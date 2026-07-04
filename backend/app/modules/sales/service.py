from __future__ import annotations

import datetime
import json
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApprovalRequired, BusinessRuleViolation, NotFoundError
from app.modules.master_data.models import Customer, PaymentTerms, Product
from app.modules.master_data.service import get_conversion_factor
from app.modules.organization.models import Branch, Warehouse

from . import models, schemas

# ---------------------------------------------------------------------------
# Helpers: scoping / lookup
# ---------------------------------------------------------------------------


def _get_branch(db: Session, branch_id: int, company_id: int) -> Branch:
    branch = db.get(Branch, branch_id)
    if branch is None or branch.company_id != company_id or branch.is_deleted:
        raise NotFoundError(f"Branch {branch_id} not found")
    return branch


def _get_customer(db: Session, customer_id: int, company_id: int) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None or customer.company_id != company_id or customer.is_deleted:
        raise NotFoundError(f"Customer {customer_id} not found")
    return customer


def _get_product(db: Session, product_id: int, company_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None or product.company_id != company_id or product.is_deleted:
        raise NotFoundError(f"Product {product_id} not found")
    return product


def _get_warehouse_company_id(db: Session, warehouse_id: int) -> int:
    wh = db.get(Warehouse, warehouse_id)
    if wh is None or wh.is_deleted:
        raise NotFoundError(f"Warehouse {warehouse_id} not found")
    branch = db.get(Branch, wh.branch_id)
    if branch is None or branch.is_deleted:
        raise NotFoundError(f"Branch for warehouse {warehouse_id} not found")
    return branch.company_id


def _assert_warehouse_in_company(db: Session, warehouse_id: int, company_id: int) -> None:
    if _get_warehouse_company_id(db, warehouse_id) != company_id:
        raise NotFoundError(f"Warehouse {warehouse_id} not found")


# ---------------------------------------------------------------------------
# SalesSettings
# ---------------------------------------------------------------------------


def get_or_create_settings(db: Session, company_id: int) -> models.SalesSettings:
    stmt = select(models.SalesSettings).where(models.SalesSettings.company_id == company_id)
    settings = db.scalars(stmt).first()
    if settings is None:
        settings = models.SalesSettings(company_id=company_id)
        db.add(settings)
        db.flush()
    return settings


def update_settings(
    db: Session,
    payload: schemas.SalesSettingsUpdate,
    company_id: int,
    actor_id: int | None = None,
) -> models.SalesSettings:
    settings = get_or_create_settings(db, company_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings, field, value)
    settings.updated_by = actor_id
    db.flush()
    return settings


# ---------------------------------------------------------------------------
# Sequence numbers (race-safe via SELECT FOR UPDATE on settings row)
# ---------------------------------------------------------------------------


def _next_invoice_number(db: Session, company_id: int) -> str:
    stmt = (
        select(models.SalesSettings)
        .where(models.SalesSettings.company_id == company_id)
        .with_for_update()
    )
    settings = db.scalars(stmt).first()
    if settings is None:
        settings = models.SalesSettings(company_id=company_id)
        db.add(settings)
        db.flush()
    n = settings.next_invoice_number
    settings.next_invoice_number = n + 1
    db.flush()
    year = datetime.date.today().year
    return f"INV-{year}-{n:05d}"


def _next_credit_note_number(db: Session, company_id: int) -> str:
    stmt = (
        select(models.SalesSettings)
        .where(models.SalesSettings.company_id == company_id)
        .with_for_update()
    )
    settings = db.scalars(stmt).first()
    if settings is None:
        settings = models.SalesSettings(company_id=company_id)
        db.add(settings)
        db.flush()
    n = settings.next_credit_note_number
    settings.next_credit_note_number = n + 1
    db.flush()
    year = datetime.date.today().year
    return f"CN-{year}-{n:05d}"


def _next_collection_number(db: Session, company_id: int) -> str:
    stmt = (
        select(models.SalesSettings)
        .where(models.SalesSettings.company_id == company_id)
        .with_for_update()
    )
    settings = db.scalars(stmt).first()
    if settings is None:
        settings = models.SalesSettings(company_id=company_id)
        db.add(settings)
        db.flush()
    n = settings.next_collection_number
    settings.next_collection_number = n + 1
    db.flush()
    year = datetime.date.today().year
    return f"COL-{year}-{n:05d}"


# ---------------------------------------------------------------------------
# PriceList CRUD
# ---------------------------------------------------------------------------


def create_price_list(
    db: Session,
    payload: schemas.PriceListCreate,
    company_id: int,
    actor_id: int | None = None,
) -> models.PriceList:
    if payload.is_default:
        _clear_default_price_list(db, company_id)
    pl = models.PriceList(
        company_id=company_id,
        code=payload.code,
        name_en=payload.name_en,
        name_ar=payload.name_ar,
        is_default=payload.is_default,
        is_active=payload.is_active,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(pl)
    db.flush()
    return pl


def _clear_default_price_list(db: Session, company_id: int) -> None:
    stmt = select(models.PriceList).where(
        models.PriceList.company_id == company_id,
        models.PriceList.is_default.is_(True),
        models.PriceList.is_deleted.is_(False),
    )
    existing = db.scalars(stmt).first()
    if existing is not None:
        existing.is_default = False
        db.flush()


def get_price_list(db: Session, price_list_id: int, company_id: int) -> models.PriceList:
    pl = db.get(models.PriceList, price_list_id)
    if pl is None or pl.company_id != company_id or pl.is_deleted:
        raise NotFoundError(f"PriceList {price_list_id} not found")
    return pl


def list_price_lists(
    db: Session, company_id: int, include_deleted: bool = False
) -> list[models.PriceList]:
    stmt = select(models.PriceList).where(models.PriceList.company_id == company_id)
    if not include_deleted:
        stmt = stmt.where(models.PriceList.is_deleted.is_(False))
    return list(db.scalars(stmt.order_by(models.PriceList.id)))


def update_price_list(
    db: Session,
    price_list_id: int,
    payload: schemas.PriceListUpdate,
    company_id: int,
    actor_id: int | None = None,
) -> models.PriceList:
    pl = get_price_list(db, price_list_id, company_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("is_default") is True:
        _clear_default_price_list(db, company_id)
    for field, value in data.items():
        setattr(pl, field, value)
    pl.updated_by = actor_id
    db.flush()
    return pl


# --- PriceListItems ---------------------------------------------------------


def add_price_list_item(
    db: Session,
    price_list_id: int,
    payload: schemas.PriceListItemCreate,
    company_id: int,
    actor_id: int | None = None,
) -> models.PriceListItem:
    get_price_list(db, price_list_id, company_id)
    _get_product(db, payload.product_id, company_id)
    item = models.PriceListItem(
        price_list_id=price_list_id,
        product_id=payload.product_id,
        unit_price=payload.unit_price,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(item)
    db.flush()
    return item


def update_price_list_item(
    db: Session,
    item_id: int,
    payload: schemas.PriceListItemUpdate,
    company_id: int,
    actor_id: int | None = None,
) -> models.PriceListItem:
    item = db.get(models.PriceListItem, item_id)
    if item is None or item.is_deleted:
        raise NotFoundError(f"PriceListItem {item_id} not found")
    pl = db.get(models.PriceList, item.price_list_id)
    if pl is None or pl.company_id != company_id:
        raise NotFoundError(f"PriceListItem {item_id} not found")
    item.unit_price = payload.unit_price
    item.updated_by = actor_id
    db.flush()
    return item


def list_price_list_items(
    db: Session, price_list_id: int, company_id: int
) -> list[models.PriceListItem]:
    get_price_list(db, price_list_id, company_id)
    stmt = select(models.PriceListItem).where(
        models.PriceListItem.price_list_id == price_list_id,
        models.PriceListItem.is_deleted.is_(False),
    )
    return list(db.scalars(stmt.order_by(models.PriceListItem.id)))


def _lookup_price(
    db: Session, price_list_id: int, product_id: int
) -> Decimal | None:
    stmt = select(models.PriceListItem).where(
        models.PriceListItem.price_list_id == price_list_id,
        models.PriceListItem.product_id == product_id,
        models.PriceListItem.is_deleted.is_(False),
    )
    item = db.scalars(stmt).first()
    return item.unit_price if item is not None else None


# ---------------------------------------------------------------------------
# ApprovalRequest helpers
# ---------------------------------------------------------------------------


def _find_approval(
    db: Session,
    request_type: models.ApprovalRequestType,
    reference_type: str,
    reference_id: int,
    status: models.ApprovalStatus | None = None,
) -> models.ApprovalRequest | None:
    stmt = select(models.ApprovalRequest).where(
        models.ApprovalRequest.request_type == request_type,
        models.ApprovalRequest.reference_type == reference_type,
        models.ApprovalRequest.reference_id == reference_id,
    )
    if status is not None:
        stmt = stmt.where(models.ApprovalRequest.status == status)
    return db.scalars(stmt.order_by(models.ApprovalRequest.id.desc())).first()


def _require_approval(
    db: Session,
    company_id: int,
    request_type: models.ApprovalRequestType,
    reference_type: str,
    reference_id: int,
    requested_by: int | None,
    detail: str,
    metadata: dict | None = None,
) -> None:
    """Check for APPROVED approval; if not found, create PENDING and raise."""
    approved = _find_approval(
        db, request_type, reference_type, reference_id, models.ApprovalStatus.APPROVED
    )
    if approved is not None:
        return  # previously approved — proceed

    rejected = _find_approval(
        db, request_type, reference_type, reference_id, models.ApprovalStatus.REJECTED
    )
    if rejected is not None:
        raise BusinessRuleViolation(
            f"Approval #{rejected.id} for this operation was rejected"
        )

    pending = _find_approval(
        db, request_type, reference_type, reference_id, models.ApprovalStatus.PENDING
    )
    if pending is not None:
        raise ApprovalRequired(pending.id, f"Approval #{pending.id} is pending: {detail}")

    req = models.ApprovalRequest(
        company_id=company_id,
        request_type=request_type,
        reference_type=reference_type,
        reference_id=reference_id,
        requested_by=requested_by,
        approval_metadata=json.dumps(metadata) if metadata else None,
    )
    db.add(req)
    db.flush()
    raise ApprovalRequired(req.id, f"Approval #{req.id} created: {detail}")


def approve_request(
    db: Session,
    approval_id: int,
    company_id: int,
    actor_id: int,
) -> models.ApprovalRequest:
    req = db.get(models.ApprovalRequest, approval_id)
    if req is None or req.company_id != company_id:
        raise NotFoundError(f"ApprovalRequest {approval_id} not found")
    if req.status != models.ApprovalStatus.PENDING:
        raise BusinessRuleViolation(f"ApprovalRequest {approval_id} is already {req.status}")
    if req.requested_by == actor_id:
        raise BusinessRuleViolation("The requester cannot approve their own request (maker-checker)")
    req.status = models.ApprovalStatus.APPROVED
    req.approved_by = actor_id
    req.decided_at = datetime.datetime.now(datetime.UTC)
    db.flush()
    return req


def reject_request(
    db: Session,
    approval_id: int,
    company_id: int,
    actor_id: int,
    reason: str,
) -> models.ApprovalRequest:
    req = db.get(models.ApprovalRequest, approval_id)
    if req is None or req.company_id != company_id:
        raise NotFoundError(f"ApprovalRequest {approval_id} not found")
    if req.status != models.ApprovalStatus.PENDING:
        raise BusinessRuleViolation(f"ApprovalRequest {approval_id} is already {req.status}")
    if req.requested_by == actor_id:
        raise BusinessRuleViolation("The requester cannot reject their own request (maker-checker)")
    req.status = models.ApprovalStatus.REJECTED
    req.approved_by = actor_id
    req.reason = reason
    req.decided_at = datetime.datetime.now(datetime.UTC)
    db.flush()
    return req


def get_approval_request(
    db: Session, approval_id: int, company_id: int
) -> models.ApprovalRequest:
    req = db.get(models.ApprovalRequest, approval_id)
    if req is None or req.company_id != company_id:
        raise NotFoundError(f"ApprovalRequest {approval_id} not found")
    return req


def list_approval_requests(
    db: Session,
    company_id: int,
    status: models.ApprovalStatus | None = None,
    reference_type: str | None = None,
) -> list[models.ApprovalRequest]:
    stmt = select(models.ApprovalRequest).where(
        models.ApprovalRequest.company_id == company_id
    )
    if status is not None:
        stmt = stmt.where(models.ApprovalRequest.status == status)
    if reference_type is not None:
        stmt = stmt.where(models.ApprovalRequest.reference_type == reference_type)
    return list(db.scalars(stmt.order_by(models.ApprovalRequest.id.desc())))


# ---------------------------------------------------------------------------
# Invoice validation helpers
# ---------------------------------------------------------------------------


def _compute_credit_exposure(db: Session, customer_id: int) -> Decimal:
    """Live sum of open receivables: grand_total - amount_collected for all
    POSTED/COLLECTED invoices that are not CANCELLED/CLOSED."""
    stmt = select(models.SalesInvoice).where(
        models.SalesInvoice.customer_id == customer_id,
        models.SalesInvoice.status.in_(
            [models.InvoiceStatus.POSTED, models.InvoiceStatus.COLLECTED]
        ),
        models.SalesInvoice.is_deleted.is_(False),
    )
    invoices = list(db.scalars(stmt))
    return sum((inv.grand_total - inv.amount_collected for inv in invoices), Decimal(0))


def _resolve_term_days(customer: Customer) -> int:
    if customer.payment_terms == PaymentTerms.CASH:
        return 0
    return customer.payment_term_days


def _recompute_invoice_totals(invoice: models.SalesInvoice, lines: list[models.SalesInvoiceLine]) -> None:
    active_lines = [ln for ln in lines if not ln.is_deleted]
    invoice.subtotal = sum(
        (ln.quantity_delivered * ln.unit_price for ln in active_lines), Decimal(0)
    )
    invoice.total_discount = sum((ln.line_discount for ln in active_lines), Decimal(0))
    invoice.total_tax = sum((ln.line_tax for ln in active_lines), Decimal(0))
    invoice.grand_total = invoice.subtotal - invoice.total_discount + invoice.total_tax


def _get_invoice_lines(db: Session, invoice_id: int) -> list[models.SalesInvoiceLine]:
    stmt = select(models.SalesInvoiceLine).where(
        models.SalesInvoiceLine.invoice_id == invoice_id,
        models.SalesInvoiceLine.is_deleted.is_(False),
    )
    return list(db.scalars(stmt))


def _get_credit_note_lines(db: Session, cn_id: int) -> list[models.CreditNoteLine]:
    stmt = select(models.CreditNoteLine).where(
        models.CreditNoteLine.credit_note_id == cn_id,
        models.CreditNoteLine.is_deleted.is_(False),
    )
    return list(db.scalars(stmt))


# ---------------------------------------------------------------------------
# SalesInvoice CRUD
# ---------------------------------------------------------------------------


def create_invoice(
    db: Session,
    payload: schemas.SalesInvoiceCreate,
    company_id: int,
    actor_id: int | None = None,
) -> models.SalesInvoice:
    branch = _get_branch(db, payload.branch_id, company_id)  # noqa: F841
    customer = _get_customer(db, payload.customer_id, company_id)
    pl = get_price_list(db, payload.price_list_id, company_id)
    if not pl.is_active:
        raise BusinessRuleViolation(f"PriceList {pl.code} is not active")

    settings = get_or_create_settings(db, company_id)
    if not customer.is_active and not settings.allow_sale_to_inactive_customer:
        raise BusinessRuleViolation(
            f"Customer {customer.code} is inactive; enable allow_sale_to_inactive_customer"
        )

    invoice_number = _next_invoice_number(db, company_id)
    invoice = models.SalesInvoice(
        company_id=company_id,
        branch_id=payload.branch_id,
        invoice_number=invoice_number,
        customer_id=payload.customer_id,
        salesman_id=payload.salesman_id,
        price_list_id=payload.price_list_id,
        status=models.InvoiceStatus.DRAFT,
        payment_terms_type=customer.payment_terms.value,
        invoice_date=payload.invoice_date,
        notes=payload.notes,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(invoice)
    db.flush()

    lines: list[models.SalesInvoiceLine] = []
    for line_payload in payload.lines:
        line = _build_invoice_line(db, invoice, line_payload, company_id, actor_id)
        db.add(line)
        lines.append(line)
    db.flush()

    _recompute_invoice_totals(invoice, lines)
    db.flush()
    return invoice


def _build_invoice_line(
    db: Session,
    invoice: models.SalesInvoice,
    payload: schemas.InvoiceLineCreate,
    company_id: int,
    actor_id: int | None,
) -> models.SalesInvoiceLine:
    product = _get_product(db, payload.product_id, company_id)
    if not product.is_active:
        raise BusinessRuleViolation(f"Product {product.code} is not active")
    if not product.is_sellable:
        raise BusinessRuleViolation(f"Product {product.code} is not sellable")

    _assert_warehouse_in_company(db, payload.warehouse_id, company_id)

    # Validate price source — MANUAL entries need approval at POST, not here.
    if payload.price_source == models.PriceSource.PRICE_LIST:
        list_price = _lookup_price(db, invoice.price_list_id, payload.product_id)
        if list_price is None:
            raise BusinessRuleViolation(
                f"Product {product.code} has no price in the selected price list; "
                "set price_source=MANUAL to override"
            )

    line_total = (
        payload.quantity_ordered * payload.unit_price
        - payload.line_discount
        + payload.line_tax
    )
    return models.SalesInvoiceLine(
        invoice_id=invoice.id,
        product_id=payload.product_id,
        warehouse_id=payload.warehouse_id,
        batch_id=payload.batch_id,
        unit_id=payload.unit_id,
        quantity_ordered=payload.quantity_ordered,
        quantity_delivered=payload.quantity_ordered,
        unit_price=payload.unit_price,
        price_source=payload.price_source,
        line_discount=payload.line_discount,
        line_tax=payload.line_tax,
        line_total=line_total,
        created_by=actor_id,
        updated_by=actor_id,
    )


def get_invoice(
    db: Session, invoice_id: int, company_id: int
) -> models.SalesInvoice:
    inv = db.get(models.SalesInvoice, invoice_id)
    if inv is None or inv.company_id != company_id or inv.is_deleted:
        raise NotFoundError(f"SalesInvoice {invoice_id} not found")
    return inv


def get_invoice_detail(
    db: Session, invoice_id: int, company_id: int
) -> tuple[models.SalesInvoice, list[models.SalesInvoiceLine]]:
    inv = get_invoice(db, invoice_id, company_id)
    lines = _get_invoice_lines(db, invoice_id)
    return inv, lines


def list_invoices(
    db: Session,
    company_id: int,
    customer_id: int | None = None,
    status: models.InvoiceStatus | None = None,
) -> list[models.SalesInvoice]:
    stmt = select(models.SalesInvoice).where(
        models.SalesInvoice.company_id == company_id,
        models.SalesInvoice.is_deleted.is_(False),
    )
    if customer_id is not None:
        stmt = stmt.where(models.SalesInvoice.customer_id == customer_id)
    if status is not None:
        stmt = stmt.where(models.SalesInvoice.status == status)
    return list(db.scalars(stmt.order_by(models.SalesInvoice.id.desc())))


# ---------------------------------------------------------------------------
# post_invoice — atomic, idempotent on re-call
# ---------------------------------------------------------------------------


def post_invoice(
    db: Session,
    invoice_id: int,
    company_id: int,
    actor_id: int | None = None,
) -> models.SalesInvoice:
    from app.modules.inventory import schemas as inv_schemas
    from app.modules.inventory import service as inv_service

    invoice = get_invoice(db, invoice_id, company_id)
    if invoice.status not in (models.InvoiceStatus.DRAFT, models.InvoiceStatus.APPROVED):
        raise BusinessRuleViolation(
            f"Cannot post invoice with status {invoice.status}"
        )

    lines = _get_invoice_lines(db, invoice_id)
    if not lines:
        raise BusinessRuleViolation("Invoice has no lines")

    settings = get_or_create_settings(db, company_id)
    customer = _get_customer(db, invoice.customer_id, company_id)

    # ── VALIDATION PASS ───────────────────────────────────────────────────

    # Backdated invoice check
    posted_date = datetime.date.today()
    if invoice.invoice_date < posted_date and not settings.allow_backdated_invoice:
        _require_approval(
            db,
            company_id=company_id,
            request_type=models.ApprovalRequestType.BACKDATED_INVOICE,
            reference_type="sales_invoice",
            reference_id=invoice_id,
            requested_by=actor_id,
            detail=(
                f"Invoice date {invoice.invoice_date} is before posting date {posted_date}"
            ),
            metadata={"invoice_date": str(invoice.invoice_date), "posted_date": str(posted_date)},
        )

    for line in lines:
        product = _get_product(db, line.product_id, company_id)

        # Manual price approval
        if line.price_source == models.PriceSource.MANUAL:
            _require_approval(
                db,
                company_id=company_id,
                request_type=models.ApprovalRequestType.MANUAL_PRICE,
                reference_type="sales_invoice_line",
                reference_id=line.id,
                requested_by=actor_id,
                detail=f"Manual price {line.unit_price} on product {product.code}",
                metadata={
                    "product_id": product.id,
                    "product_code": product.code,
                    "unit_price": str(line.unit_price),
                },
            )

        # Discount approval
        if line.line_discount > 0 and line.quantity_delivered > 0:
            discount_pct = (line.line_discount / (line.quantity_delivered * line.unit_price) * 100
                            if line.unit_price > 0 else Decimal(0))
            max_pct = _get_actor_max_discount(db, actor_id, company_id)
            if discount_pct > max_pct:
                _require_approval(
                    db,
                    company_id=company_id,
                    request_type=models.ApprovalRequestType.DISCOUNT_OVERRIDE,
                    reference_type="sales_invoice_line",
                    reference_id=line.id,
                    requested_by=actor_id,
                    detail=(
                        f"Discount {discount_pct:.2f}% exceeds your limit {max_pct:.2f}% "
                        f"on product {product.code}"
                    ),
                    metadata={
                        "discount_pct": str(discount_pct),
                        "max_allowed_pct": str(max_pct),
                    },
                )

        # Stock availability
        neg_stock_approved = _find_approval(
            db,
            models.ApprovalRequestType.NEGATIVE_STOCK,
            "sales_invoice_line",
            line.id,
            models.ApprovalStatus.APPROVED,
        ) is not None
        if not (settings.allow_negative_stock_on_sale or neg_stock_approved):
            _check_stock_for_line(db, line, company_id, product)

    # Credit limit check (whole invoice)
    if customer.credit_limit is not None and invoice.payment_terms_type == PaymentTerms.CREDIT:
        exposure = _compute_credit_exposure(db, customer.id)
        if exposure + invoice.grand_total > customer.credit_limit:
            _require_approval(
                db,
                company_id=company_id,
                request_type=models.ApprovalRequestType.CREDIT_LIMIT_OVERRIDE,
                reference_type="sales_invoice",
                reference_id=invoice_id,
                requested_by=actor_id,
                detail=(
                    f"Credit limit {customer.credit_limit} exceeded: "
                    f"exposure={exposure}, invoice={invoice.grand_total}"
                ),
                metadata={
                    "credit_limit": str(customer.credit_limit),
                    "current_exposure": str(exposure),
                    "invoice_amount": str(invoice.grand_total),
                },
            )

    # ── EXECUTION PASS (all checks passed) ────────────────────────────────
    for line in lines:
        neg_stock_approved = _find_approval(
            db,
            models.ApprovalRequestType.NEGATIVE_STOCK,
            "sales_invoice_line",
            line.id,
            models.ApprovalStatus.APPROVED,
        ) is not None

        # Convert selling unit quantity to base unit for stock issue
        product = _get_product(db, line.product_id, company_id)
        base_qty = _to_base_qty(db, company_id, line, product)

        mv = inv_service.issue_stock(
            db,
            inv_schemas.IssueStockRequest(
                warehouse_id=line.warehouse_id,
                product_id=line.product_id,
                batch_id=line.batch_id,
                quantity=base_qty,
                notes=f"Sale invoice {invoice.invoice_number}",
                approved_negative=neg_stock_approved,
            ),
            company_id=company_id,
            actor_id=actor_id,
        )
        line.stock_movement_id = mv.id
        db.flush()

    term_days = _resolve_term_days(customer)
    invoice.due_date = posted_date + datetime.timedelta(days=term_days)
    invoice.status = models.InvoiceStatus.POSTED
    invoice.posted_at = datetime.datetime.now(datetime.UTC)
    invoice.updated_by = actor_id
    db.flush()
    return invoice


def _to_base_qty(
    db: Session,
    company_id: int,
    line: models.SalesInvoiceLine,
    product: Product,
) -> Decimal:
    if line.unit_id == product.base_unit_id:
        return line.quantity_delivered
    factor = get_conversion_factor(
        db, company_id, line.unit_id, product.base_unit_id, product_id=product.id
    )
    return (line.quantity_delivered * factor).quantize(Decimal("0.000001"))


def _get_actor_max_discount(
    db: Session, actor_id: int | None, company_id: int
) -> Decimal:
    if actor_id is None:
        return Decimal(0)
    from app.modules.auth.models import Role, UserRole
    stmt = (
        select(Role.max_discount_pct)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(
            UserRole.user_id == actor_id,
            Role.company_id == company_id,
            Role.is_deleted.is_(False),
        )
    )
    results = list(db.scalars(stmt))
    return max(results, default=Decimal(0))


def _check_stock_for_line(
    db: Session,
    line: models.SalesInvoiceLine,
    company_id: int,
    product: Product,
) -> None:
    from app.modules.inventory.models import StockBalance

    base_qty = _to_base_qty(
        db,
        company_id,
        line,
        product,
    )
    if line.batch_id is None:
        stmt = select(StockBalance).where(
            StockBalance.company_id == company_id,
            StockBalance.warehouse_id == line.warehouse_id,
            StockBalance.product_id == line.product_id,
            StockBalance.batch_id.is_(None),
        )
    else:
        stmt = select(StockBalance).where(
            StockBalance.company_id == company_id,
            StockBalance.warehouse_id == line.warehouse_id,
            StockBalance.product_id == line.product_id,
            StockBalance.batch_id == line.batch_id,
        )
    balance = db.scalars(stmt).first()
    on_hand = balance.quantity_on_hand if balance is not None else Decimal(0)
    if on_hand - base_qty < 0:
        raise BusinessRuleViolation(
            f"Insufficient stock for product {product.code}: "
            f"on_hand={on_hand}, requested={base_qty}"
        )


# ---------------------------------------------------------------------------
# cancel_invoice
# ---------------------------------------------------------------------------


def cancel_invoice(
    db: Session,
    invoice_id: int,
    company_id: int,
    actor_id: int | None = None,
    reason: str | None = None,
) -> models.SalesInvoice:
    from app.modules.inventory import service as inv_service

    invoice = get_invoice(db, invoice_id, company_id)

    if invoice.status in (
        models.InvoiceStatus.DRAFT,
        models.InvoiceStatus.PENDING_APPROVAL,
        models.InvoiceStatus.APPROVED,
    ):
        invoice.status = models.InvoiceStatus.CANCELLED
        invoice.updated_by = actor_id
        db.flush()
        return invoice

    if invoice.status != models.InvoiceStatus.POSTED:
        raise BusinessRuleViolation(
            f"Cannot cancel invoice with status {invoice.status}"
        )

    _require_approval(
        db,
        company_id=company_id,
        request_type=models.ApprovalRequestType.CANCEL_AFTER_POST,
        reference_type="sales_invoice",
        reference_id=invoice_id,
        requested_by=actor_id,
        detail=f"Cancel posted invoice {invoice.invoice_number}",
        metadata={"reason": reason, "invoice_number": invoice.invoice_number},
    )

    # Approved — reverse all stock movements atomically
    lines = _get_invoice_lines(db, invoice_id)
    for line in lines:
        if line.stock_movement_id is not None:
            inv_service.reverse_movement(
                db,
                line.stock_movement_id,
                company_id=company_id,
                actor_id=actor_id,
                notes=f"Cancellation of invoice {invoice.invoice_number}",
            )

    invoice.status = models.InvoiceStatus.CANCELLED
    invoice.updated_by = actor_id
    db.flush()
    return invoice


# ---------------------------------------------------------------------------
# CreditNote
# ---------------------------------------------------------------------------


def create_credit_note(
    db: Session,
    payload: schemas.CreditNoteCreate,
    company_id: int,
    actor_id: int | None = None,
) -> models.CreditNote:
    original = get_invoice(db, payload.original_invoice_id, company_id)
    if original.status != models.InvoiceStatus.POSTED:
        raise BusinessRuleViolation(
            f"Credit notes can only be raised against POSTED invoices "
            f"(invoice status: {original.status})"
        )

    cn_number = _next_credit_note_number(db, company_id)
    cn = models.CreditNote(
        company_id=company_id,
        branch_id=original.branch_id,
        credit_note_number=cn_number,
        original_invoice_id=original.id,
        customer_id=original.customer_id,
        status=models.CreditNoteStatus.DRAFT,
        reason=payload.reason,
        credit_note_date=payload.credit_note_date,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(cn)
    db.flush()

    cn_lines: list[models.CreditNoteLine] = []
    for line_payload in payload.lines:
        cn_line = _build_cn_line(db, cn, line_payload, company_id, actor_id)
        db.add(cn_line)
        cn_lines.append(cn_line)
    db.flush()

    cn.subtotal = sum((ln.line_total for ln in cn_lines), Decimal(0))
    cn.total_tax = Decimal(0)
    cn.total = cn.subtotal + cn.total_tax
    db.flush()
    return cn


def _build_cn_line(
    db: Session,
    cn: models.CreditNote,
    payload: schemas.CreditNoteLineCreate,
    company_id: int,
    actor_id: int | None,
) -> models.CreditNoteLine:
    orig_line = db.get(models.SalesInvoiceLine, payload.original_line_id)
    if orig_line is None or orig_line.is_deleted:
        raise NotFoundError(f"SalesInvoiceLine {payload.original_line_id} not found")
    if orig_line.invoice_id != cn.original_invoice_id:
        raise BusinessRuleViolation(
            f"Line {payload.original_line_id} does not belong to invoice {cn.original_invoice_id}"
        )

    # Returnable quantity guard
    already_returned = _total_returned(db, payload.original_line_id)
    if already_returned + payload.quantity_returned > orig_line.quantity_delivered:
        raise BusinessRuleViolation(
            f"Cannot return {payload.quantity_returned}: "
            f"delivered={orig_line.quantity_delivered}, already returned={already_returned}"
        )

    line_total = payload.quantity_returned * orig_line.unit_price
    return models.CreditNoteLine(
        credit_note_id=cn.id,
        original_line_id=orig_line.id,
        product_id=orig_line.product_id,
        warehouse_id=orig_line.warehouse_id,
        batch_id=orig_line.batch_id,
        unit_id=orig_line.unit_id,
        quantity_returned=payload.quantity_returned,
        unit_price=orig_line.unit_price,
        line_total=line_total,
        created_by=actor_id,
        updated_by=actor_id,
    )


def _total_returned(db: Session, original_line_id: int) -> Decimal:
    stmt = (
        select(models.CreditNoteLine)
        .join(models.CreditNote, models.CreditNote.id == models.CreditNoteLine.credit_note_id)
        .where(
            models.CreditNoteLine.original_line_id == original_line_id,
            models.CreditNoteLine.is_deleted.is_(False),
            models.CreditNote.status == models.CreditNoteStatus.POSTED,
        )
    )
    lines = list(db.scalars(stmt))
    return sum((ln.quantity_returned for ln in lines), Decimal(0))


def get_credit_note(
    db: Session, cn_id: int, company_id: int
) -> models.CreditNote:
    cn = db.get(models.CreditNote, cn_id)
    if cn is None or cn.company_id != company_id or cn.is_deleted:
        raise NotFoundError(f"CreditNote {cn_id} not found")
    return cn


def get_credit_note_detail(
    db: Session, cn_id: int, company_id: int
) -> tuple[models.CreditNote, list[models.CreditNoteLine]]:
    cn = get_credit_note(db, cn_id, company_id)
    lines = _get_credit_note_lines(db, cn_id)
    return cn, lines


def list_credit_notes(
    db: Session,
    company_id: int,
    customer_id: int | None = None,
) -> list[models.CreditNote]:
    stmt = select(models.CreditNote).where(
        models.CreditNote.company_id == company_id,
        models.CreditNote.is_deleted.is_(False),
    )
    if customer_id is not None:
        stmt = stmt.where(models.CreditNote.customer_id == customer_id)
    return list(db.scalars(stmt.order_by(models.CreditNote.id.desc())))


def post_credit_note(
    db: Session,
    cn_id: int,
    company_id: int,
    actor_id: int | None = None,
) -> models.CreditNote:
    from app.modules.inventory import schemas as inv_schemas
    from app.modules.inventory import service as inv_service

    cn = get_credit_note(db, cn_id, company_id)
    if cn.status != models.CreditNoteStatus.DRAFT:
        raise BusinessRuleViolation(f"Cannot post credit note with status {cn.status}")

    lines = _get_credit_note_lines(db, cn_id)
    if not lines:
        raise BusinessRuleViolation("Credit note has no lines")

    for line in lines:
        orig_line = db.get(models.SalesInvoiceLine, line.original_line_id)
        product = _get_product(db, line.product_id, company_id)

        base_qty = _to_base_qty_cn(db, company_id, line, product)

        mv = inv_service.receive_stock(
            db,
            inv_schemas.ReceiveStockRequest(
                warehouse_id=orig_line.warehouse_id,
                product_id=orig_line.product_id,
                batch_id=orig_line.batch_id,
                quantity=base_qty,
                unit_cost=orig_line.unit_price,
                notes=f"Return: credit note {cn.credit_note_number}",
            ),
            company_id=company_id,
            actor_id=actor_id,
        )
        line.stock_movement_id = mv.id
        db.flush()

    cn.status = models.CreditNoteStatus.POSTED
    cn.updated_by = actor_id
    db.flush()
    return cn


def _to_base_qty_cn(
    db: Session,
    company_id: int,
    line: models.CreditNoteLine,
    product: Product,
) -> Decimal:
    if line.unit_id == product.base_unit_id:
        return line.quantity_returned
    factor = get_conversion_factor(
        db, company_id, line.unit_id, product.base_unit_id, product_id=product.id
    )
    return (line.quantity_returned * factor).quantize(Decimal("0.000001"))


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------


def create_collection(
    db: Session,
    payload: schemas.CollectionCreate,
    company_id: int,
    actor_id: int | None = None,
) -> models.Collection:
    _get_branch(db, payload.branch_id, company_id)
    _get_customer(db, payload.customer_id, company_id)

    collection_number = _next_collection_number(db, company_id)
    col = models.Collection(
        company_id=company_id,
        branch_id=payload.branch_id,
        collection_number=collection_number,
        customer_id=payload.customer_id,
        salesman_id=payload.salesman_id,
        collection_date=payload.collection_date,
        total_amount=payload.total_amount,
        allocation_method=payload.allocation_method,
        status=models.CollectionStatus.DRAFT,
        notes=payload.notes,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(col)
    db.flush()

    if payload.allocation_method == models.AllocationMethod.MANUAL and payload.lines:
        for lp in payload.lines:
            inv = db.get(models.SalesInvoice, lp.invoice_id)
            if inv is None or inv.customer_id != payload.customer_id or inv.company_id != company_id:
                raise NotFoundError(f"SalesInvoice {lp.invoice_id} not found for this customer")
            cl = models.CollectionLine(
                collection_id=col.id,
                invoice_id=lp.invoice_id,
                amount_allocated=lp.amount_allocated,
                created_by=actor_id,
                updated_by=actor_id,
            )
            db.add(cl)
        db.flush()

    return col


def get_collection(db: Session, collection_id: int, company_id: int) -> models.Collection:
    col = db.get(models.Collection, collection_id)
    if col is None or col.company_id != company_id or col.is_deleted:
        raise NotFoundError(f"Collection {collection_id} not found")
    return col


def get_collection_detail(
    db: Session, collection_id: int, company_id: int
) -> tuple[models.Collection, list[models.CollectionLine]]:
    col = get_collection(db, collection_id, company_id)
    stmt = select(models.CollectionLine).where(
        models.CollectionLine.collection_id == collection_id
    )
    lines = list(db.scalars(stmt))
    return col, lines


def list_collections(
    db: Session,
    company_id: int,
    customer_id: int | None = None,
) -> list[models.Collection]:
    stmt = select(models.Collection).where(
        models.Collection.company_id == company_id,
        models.Collection.is_deleted.is_(False),
    )
    if customer_id is not None:
        stmt = stmt.where(models.Collection.customer_id == customer_id)
    return list(db.scalars(stmt.order_by(models.Collection.id.desc())))


def post_collection(
    db: Session,
    collection_id: int,
    company_id: int,
    actor_id: int | None = None,
) -> models.Collection:
    col = get_collection(db, collection_id, company_id)
    if col.status != models.CollectionStatus.DRAFT:
        raise BusinessRuleViolation(f"Cannot post collection with status {col.status}")

    if col.allocation_method == models.AllocationMethod.AUTO:
        _auto_allocate(db, col, actor_id)
    else:
        _apply_manual_allocations(db, col, actor_id)

    col.status = models.CollectionStatus.POSTED
    col.updated_by = actor_id
    db.flush()
    return col


def _auto_allocate(
    db: Session, col: models.Collection, actor_id: int | None
) -> None:
    """FIFO by due_date (oldest due first)."""
    stmt = (
        select(models.SalesInvoice)
        .where(
            models.SalesInvoice.customer_id == col.customer_id,
            models.SalesInvoice.company_id == col.company_id,
            models.SalesInvoice.status == models.InvoiceStatus.POSTED,
            models.SalesInvoice.is_deleted.is_(False),
        )
        .order_by(models.SalesInvoice.due_date.nulls_last(), models.SalesInvoice.id)
    )
    invoices = list(db.scalars(stmt))

    remaining = col.total_amount
    for inv in invoices:
        if remaining <= 0:
            break
        open_amount = inv.grand_total - inv.amount_collected
        if open_amount <= 0:
            continue
        allocate = min(open_amount, remaining)
        cl = models.CollectionLine(
            collection_id=col.id,
            invoice_id=inv.id,
            amount_allocated=allocate,
            created_by=actor_id,
            updated_by=actor_id,
        )
        db.add(cl)
        inv.amount_collected += allocate
        if inv.amount_collected >= inv.grand_total:
            inv.status = models.InvoiceStatus.COLLECTED
        inv.updated_by = actor_id
        db.flush()
        remaining -= allocate


def _apply_manual_allocations(
    db: Session, col: models.Collection, actor_id: int | None
) -> None:
    stmt = select(models.CollectionLine).where(
        models.CollectionLine.collection_id == col.id
    )
    lines = list(db.scalars(stmt))
    total_allocated = sum((ln.amount_allocated for ln in lines), Decimal(0))
    if total_allocated > col.total_amount:
        raise BusinessRuleViolation(
            f"Total allocated {total_allocated} exceeds collection amount {col.total_amount}"
        )
    for ln in lines:
        inv = db.get(models.SalesInvoice, ln.invoice_id)
        if inv is None or inv.status not in (
            models.InvoiceStatus.POSTED, models.InvoiceStatus.COLLECTED
        ):
            raise BusinessRuleViolation(
                f"Invoice {ln.invoice_id} is not in a state that accepts payment"
            )
        inv.amount_collected += ln.amount_allocated
        if inv.amount_collected >= inv.grand_total:
            inv.status = models.InvoiceStatus.COLLECTED
        inv.updated_by = actor_id
        db.flush()


def cancel_collection(
    db: Session,
    collection_id: int,
    company_id: int,
    actor_id: int | None = None,
) -> models.Collection:
    col = get_collection(db, collection_id, company_id)
    if col.status == models.CollectionStatus.CANCELLED:
        return col
    if col.status == models.CollectionStatus.POSTED:
        # Reverse all allocations
        stmt = select(models.CollectionLine).where(
            models.CollectionLine.collection_id == collection_id
        )
        lines = list(db.scalars(stmt))
        for ln in lines:
            inv = db.get(models.SalesInvoice, ln.invoice_id)
            if inv is not None:
                inv.amount_collected -= ln.amount_allocated
                if inv.status == models.InvoiceStatus.COLLECTED:
                    inv.status = models.InvoiceStatus.POSTED
                inv.updated_by = actor_id
                db.flush()
    col.status = models.CollectionStatus.CANCELLED
    col.updated_by = actor_id
    db.flush()
    return col
