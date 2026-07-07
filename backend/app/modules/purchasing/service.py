from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApprovalRequired, BusinessRuleViolation, NotFoundError  # noqa: F401
from app.modules.master_data.models import Product, Supplier
from app.modules.master_data.service import get_conversion_factor
from app.modules.organization.models import Branch, Warehouse
from app.modules.shared.models import ApprovalRequestType
from app.modules.shared.service import (
    _find_approval,
    _require_approval,
    approve_request,
    get_approval_request,
    list_approval_requests,
    reject_request,
)

from . import models, schemas

# Re-export approval helpers so callers can use p_service.approve_request(...)
__all__ = [
    "approve_request",
    "reject_request",
    "get_approval_request",
    "list_approval_requests",
]

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_branch(db: Session, branch_id: int, company_id: int) -> Branch:
    branch = db.get(Branch, branch_id)
    if branch is None or branch.company_id != company_id or branch.is_deleted:
        raise NotFoundError(f"Branch {branch_id} not found")
    return branch


def _get_supplier(db: Session, supplier_id: int, company_id: int) -> Supplier:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None or supplier.company_id != company_id or supplier.is_deleted:
        raise NotFoundError(f"Supplier {supplier_id} not found")
    return supplier


def _get_product(db: Session, product_id: int, company_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None or product.company_id != company_id or product.is_deleted:
        raise NotFoundError(f"Product {product_id} not found")
    return product


def _get_warehouse(db: Session, warehouse_id: int, company_id: int) -> Warehouse:
    wh = db.get(Warehouse, warehouse_id)
    if wh is None or wh.is_deleted:
        raise NotFoundError(f"Warehouse {warehouse_id} not found")
    branch = db.get(Branch, wh.branch_id)
    if branch is None or branch.is_deleted or branch.company_id != company_id:
        raise NotFoundError(f"Warehouse {warehouse_id} not found")
    return wh


def _to_base_qty(
    db: Session, company_id: int, qty_in_unit: Decimal, unit_id: int, product: Product
) -> Decimal:
    if unit_id == product.base_unit_id:
        return qty_in_unit
    factor = get_conversion_factor(db, company_id, unit_id, product.base_unit_id, product.id)
    return (qty_in_unit * factor).quantize(Decimal("0.000001"))


def _to_base_unit_cost(
    db: Session, company_id: int, cost_per_unit: Decimal, unit_id: int, product: Product
) -> Decimal:
    """Convert cost-per-receiving-unit to cost-per-base-unit."""
    if unit_id == product.base_unit_id:
        return cost_per_unit
    factor = get_conversion_factor(db, company_id, unit_id, product.base_unit_id, product.id)
    return (cost_per_unit / factor).quantize(Decimal("0.000001"))


def _get_grn_lines(db: Session, grn_id: int) -> list[models.GoodsReceiptLine]:
    stmt = select(models.GoodsReceiptLine).where(
        models.GoodsReceiptLine.grn_id == grn_id,
        models.GoodsReceiptLine.is_deleted.is_(False),
    )
    return list(db.scalars(stmt))


def _get_bill_lines(db: Session, bill_id: int) -> list[models.SupplierInvoiceLine]:
    stmt = select(models.SupplierInvoiceLine).where(
        models.SupplierInvoiceLine.bill_id == bill_id,
        models.SupplierInvoiceLine.is_deleted.is_(False),
    )
    return list(db.scalars(stmt))


def _get_return_lines(db: Session, return_id: int) -> list[models.PurchaseReturnLine]:
    stmt = select(models.PurchaseReturnLine).where(
        models.PurchaseReturnLine.return_id == return_id,
        models.PurchaseReturnLine.is_deleted.is_(False),
    )
    return list(db.scalars(stmt))


def _total_returned_for_grn_line(db: Session, grn_line_id: int) -> Decimal:
    stmt = (
        select(models.PurchaseReturnLine)
        .join(
            models.PurchaseReturn,
            models.PurchaseReturn.id == models.PurchaseReturnLine.return_id,
        )
        .where(
            models.PurchaseReturnLine.original_grn_line_id == grn_line_id,
            models.PurchaseReturnLine.is_deleted.is_(False),
            models.PurchaseReturn.status == models.ReturnStatus.POSTED,
        )
    )
    lines = list(db.scalars(stmt))
    return sum((ln.quantity_returned for ln in lines), Decimal(0))


# ---------------------------------------------------------------------------
# PurchaseSettings
# ---------------------------------------------------------------------------


def get_or_create_settings(db: Session, company_id: int) -> models.PurchaseSettings:
    stmt = select(models.PurchaseSettings).where(
        models.PurchaseSettings.company_id == company_id
    )
    settings = db.scalars(stmt).first()
    if settings is None:
        settings = models.PurchaseSettings(company_id=company_id)
        db.add(settings)
        db.flush()
    return settings


def update_settings(
    db: Session,
    payload: schemas.PurchaseSettingsUpdate,
    company_id: int,
    actor_id: int | None = None,
) -> models.PurchaseSettings:
    settings = get_or_create_settings(db, company_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings, field, value)
    settings.updated_by = actor_id
    db.flush()
    return settings


# ---------------------------------------------------------------------------
# Sequence numbers (SELECT FOR UPDATE on settings row)
# ---------------------------------------------------------------------------


def _next_po_number(db: Session, company_id: int) -> str:
    stmt = (
        select(models.PurchaseSettings)
        .where(models.PurchaseSettings.company_id == company_id)
        .with_for_update()
    )
    s = db.scalars(stmt).first()
    if s is None:
        s = models.PurchaseSettings(company_id=company_id)
        db.add(s)
        db.flush()
    n = s.next_po_number
    s.next_po_number = n + 1
    db.flush()
    return f"PO-{datetime.date.today().year}-{n:05d}"


def _next_grn_number(db: Session, company_id: int) -> str:
    stmt = (
        select(models.PurchaseSettings)
        .where(models.PurchaseSettings.company_id == company_id)
        .with_for_update()
    )
    s = db.scalars(stmt).first()
    if s is None:
        s = models.PurchaseSettings(company_id=company_id)
        db.add(s)
        db.flush()
    n = s.next_grn_number
    s.next_grn_number = n + 1
    db.flush()
    return f"GRN-{datetime.date.today().year}-{n:05d}"


def _next_bill_number(db: Session, company_id: int) -> str:
    stmt = (
        select(models.PurchaseSettings)
        .where(models.PurchaseSettings.company_id == company_id)
        .with_for_update()
    )
    s = db.scalars(stmt).first()
    if s is None:
        s = models.PurchaseSettings(company_id=company_id)
        db.add(s)
        db.flush()
    n = s.next_bill_number
    s.next_bill_number = n + 1
    db.flush()
    return f"BILL-{datetime.date.today().year}-{n:05d}"


def _next_payment_number(db: Session, company_id: int) -> str:
    stmt = (
        select(models.PurchaseSettings)
        .where(models.PurchaseSettings.company_id == company_id)
        .with_for_update()
    )
    s = db.scalars(stmt).first()
    if s is None:
        s = models.PurchaseSettings(company_id=company_id)
        db.add(s)
        db.flush()
    n = s.next_payment_number
    s.next_payment_number = n + 1
    db.flush()
    return f"PAY-{datetime.date.today().year}-{n:05d}"


def _next_return_number(db: Session, company_id: int) -> str:
    stmt = (
        select(models.PurchaseSettings)
        .where(models.PurchaseSettings.company_id == company_id)
        .with_for_update()
    )
    s = db.scalars(stmt).first()
    if s is None:
        s = models.PurchaseSettings(company_id=company_id)
        db.add(s)
        db.flush()
    n = s.next_return_number
    s.next_return_number = n + 1
    db.flush()
    return f"PR-{datetime.date.today().year}-{n:05d}"


# ---------------------------------------------------------------------------
# Shared checks
# ---------------------------------------------------------------------------


def _check_backdated(
    db: Session,
    company_id: int,
    doc_date: datetime.date,
    reference_type: str,
    reference_id: int,
    actor_id: int | None,
) -> None:
    if doc_date >= datetime.date.today():
        return
    settings = get_or_create_settings(db, company_id)
    if not settings.allow_backdated_purchase_docs:
        _require_approval(
            db,
            company_id=company_id,
            request_type=ApprovalRequestType.BACKDATED_PURCHASE_DOC,
            reference_type=reference_type,
            reference_id=reference_id,
            requested_by=actor_id,
            detail=(
                f"Document date {doc_date} is before posting date {datetime.date.today()}"
            ),
            metadata={"doc_date": str(doc_date), "today": str(datetime.date.today())},
        )


def _check_flow_policy(
    db: Session,
    company_id: int,
    supplier_id: int,
    purchase_order_id: int | None,
) -> None:
    settings = get_or_create_settings(db, company_id)
    policy = settings.purchase_flow_policy

    if purchase_order_id is None:
        if policy in (
            models.PurchaseFlowPolicy.PO_REQUIRED,
            models.PurchaseFlowPolicy.THREE_WAY_MATCH,
        ):
            raise BusinessRuleViolation(
                f"GRN requires an APPROVED PO under {policy} policy"
            )
    else:
        if policy == models.PurchaseFlowPolicy.THREE_WAY_MATCH:
            raise BusinessRuleViolation(
                "THREE_WAY_MATCH is not yet implemented; switch to PO_REQUIRED or DIRECT_RECEIPT"
            )
        po = get_po(db, purchase_order_id, company_id)
        if po.status != models.POStatus.APPROVED:
            raise BusinessRuleViolation(
                f"GRN can only reference an APPROVED PO (PO status: {po.status})"
            )
        if po.supplier_id != supplier_id:
            raise BusinessRuleViolation("GRN supplier does not match PO supplier")


def _compute_supplier_exposure(db: Session, supplier_id: int) -> Decimal:
    stmt = select(models.SupplierInvoice).where(
        models.SupplierInvoice.supplier_id == supplier_id,
        models.SupplierInvoice.status.in_(
            [models.BillStatus.POSTED, models.BillStatus.PAID]
        ),
        models.SupplierInvoice.is_deleted.is_(False),
    )
    invoices = list(db.scalars(stmt))
    return sum((inv.grand_total - inv.amount_paid for inv in invoices), Decimal(0))


def _update_po_status(db: Session, po_id: int) -> None:
    po = db.get(models.PurchaseOrder, po_id)
    if po is None or po.status == models.POStatus.CANCELLED:
        return
    stmt = select(models.PurchaseOrderLine).where(
        models.PurchaseOrderLine.po_id == po_id,
        models.PurchaseOrderLine.is_deleted.is_(False),
    )
    lines = list(db.scalars(stmt))
    if not lines:
        return
    if all(ln.quantity_received >= ln.quantity_ordered for ln in lines):
        po.status = models.POStatus.FULLY_RECEIVED
    elif any(ln.quantity_received > 0 for ln in lines):
        po.status = models.POStatus.PARTIALLY_RECEIVED
    db.flush()


# ---------------------------------------------------------------------------
# PurchaseOrder
# ---------------------------------------------------------------------------


def create_po(
    db: Session,
    payload: schemas.PurchaseOrderCreate,
    company_id: int,
    actor_id: int | None = None,
) -> models.PurchaseOrder:
    _get_branch(db, payload.branch_id, company_id)
    _get_supplier(db, payload.supplier_id, company_id)

    po_number = _next_po_number(db, company_id)
    po = models.PurchaseOrder(
        company_id=company_id,
        branch_id=payload.branch_id,
        supplier_id=payload.supplier_id,
        po_number=po_number,
        po_date=payload.po_date,
        status=models.POStatus.DRAFT,
        notes=payload.notes,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(po)
    db.flush()

    for lp in payload.lines:
        _get_product(db, lp.product_id, company_id)
        line = models.PurchaseOrderLine(
            po_id=po.id,
            product_id=lp.product_id,
            unit_id=lp.unit_id,
            quantity_ordered=lp.quantity_ordered,
            quantity_received=Decimal(0),
            unit_cost=lp.unit_cost,
            created_by=actor_id,
            updated_by=actor_id,
        )
        db.add(line)
    db.flush()
    return po


def approve_po(
    db: Session,
    po_id: int,
    company_id: int,
    actor_id: int | None = None,
) -> models.PurchaseOrder:
    po = get_po(db, po_id, company_id)
    if po.status != models.POStatus.DRAFT:
        raise BusinessRuleViolation(f"Cannot approve PO with status {po.status}")
    po.status = models.POStatus.APPROVED
    po.updated_by = actor_id
    db.flush()
    return po


def cancel_po(
    db: Session,
    po_id: int,
    company_id: int,
    actor_id: int | None = None,
) -> models.PurchaseOrder:
    po = get_po(db, po_id, company_id)
    if po.status not in (models.POStatus.DRAFT, models.POStatus.APPROVED):
        raise BusinessRuleViolation(
            f"Cannot cancel PO with status {po.status}"
        )
    po.status = models.POStatus.CANCELLED
    po.updated_by = actor_id
    db.flush()
    return po


def get_po(db: Session, po_id: int, company_id: int) -> models.PurchaseOrder:
    po = db.get(models.PurchaseOrder, po_id)
    if po is None or po.company_id != company_id or po.is_deleted:
        raise NotFoundError(f"PurchaseOrder {po_id} not found")
    return po


def get_po_detail(
    db: Session, po_id: int, company_id: int
) -> tuple[models.PurchaseOrder, list[models.PurchaseOrderLine]]:
    po = get_po(db, po_id, company_id)
    stmt = select(models.PurchaseOrderLine).where(
        models.PurchaseOrderLine.po_id == po_id,
        models.PurchaseOrderLine.is_deleted.is_(False),
    )
    lines = list(db.scalars(stmt))
    return po, lines


def list_pos(
    db: Session,
    company_id: int,
    supplier_id: int | None = None,
    status: models.POStatus | None = None,
) -> list[models.PurchaseOrder]:
    stmt = select(models.PurchaseOrder).where(
        models.PurchaseOrder.company_id == company_id,
        models.PurchaseOrder.is_deleted.is_(False),
    )
    if supplier_id is not None:
        stmt = stmt.where(models.PurchaseOrder.supplier_id == supplier_id)
    if status is not None:
        stmt = stmt.where(models.PurchaseOrder.status == status)
    return list(db.scalars(stmt.order_by(models.PurchaseOrder.id.desc())))


# ---------------------------------------------------------------------------
# GoodsReceipt
# ---------------------------------------------------------------------------


def create_grn(
    db: Session,
    payload: schemas.GoodsReceiptCreate,
    company_id: int,
    actor_id: int | None = None,
) -> models.GoodsReceipt:
    _get_branch(db, payload.branch_id, company_id)
    supplier = _get_supplier(db, payload.supplier_id, company_id)

    _check_flow_policy(db, company_id, supplier.id, payload.purchase_order_id)

    grn_number = _next_grn_number(db, company_id)
    grn = models.GoodsReceipt(
        company_id=company_id,
        branch_id=payload.branch_id,
        supplier_id=payload.supplier_id,
        purchase_order_id=payload.purchase_order_id,
        grn_number=grn_number,
        receipt_date=payload.receipt_date,
        status=models.GRNStatus.DRAFT,
        notes=payload.notes,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(grn)
    db.flush()

    for lp in payload.lines:
        _get_product(db, lp.product_id, company_id)
        _get_warehouse(db, lp.warehouse_id, company_id)
        line = models.GoodsReceiptLine(
            grn_id=grn.id,
            po_line_id=lp.po_line_id,
            product_id=lp.product_id,
            warehouse_id=lp.warehouse_id,
            unit_id=lp.unit_id,
            quantity_received=lp.quantity_received,
            unit_cost=lp.unit_cost,
            batch_id=lp.batch_id,
            batch_number=lp.batch_number,
            expiry_date=lp.expiry_date,
            created_by=actor_id,
            updated_by=actor_id,
        )
        db.add(line)
    db.flush()
    return grn


def post_grn(
    db: Session,
    grn_id: int,
    company_id: int,
    actor_id: int | None = None,
) -> models.GoodsReceipt:
    from app.modules.inventory import schemas as inv_schemas
    from app.modules.inventory import service as inv_service

    grn = get_grn(db, grn_id, company_id)
    if grn.status != models.GRNStatus.DRAFT:
        raise BusinessRuleViolation(f"Cannot post GRN with status {grn.status}")

    lines = _get_grn_lines(db, grn_id)
    if not lines:
        raise BusinessRuleViolation("GRN has no lines")

    settings = get_or_create_settings(db, company_id)

    # ── VALIDATION PASS ───────────────────────────────────────────────────
    _check_backdated(db, company_id, grn.receipt_date, "goods_receipt", grn_id, actor_id)

    for line in lines:
        product = _get_product(db, line.product_id, company_id)

        # Batch requirement check
        if product.is_batch_tracked and line.batch_id is None and not line.batch_number:
            raise BusinessRuleViolation(
                f"Product {product.code} is batch-tracked; "
                "provide batch_id or batch_number on the GRN line"
            )
        if not product.is_batch_tracked and line.batch_id is not None:
            raise BusinessRuleViolation(
                f"Product {product.code} is not batch-tracked; remove batch_id"
            )

        # Price variance check vs PO line
        if line.po_line_id is not None and settings.max_price_variance_pct >= 0:
            po_line = db.get(models.PurchaseOrderLine, line.po_line_id)
            if po_line is not None and po_line.unit_cost > 0:
                variance_pct = (
                    abs(line.unit_cost - po_line.unit_cost) / po_line.unit_cost * 100
                )
                if variance_pct > settings.max_price_variance_pct:
                    _require_approval(
                        db,
                        company_id=company_id,
                        request_type=ApprovalRequestType.PURCHASE_PRICE_OVERRIDE,
                        reference_type="goods_receipt_line",
                        reference_id=line.id,
                        requested_by=actor_id,
                        detail=(
                            f"GRN unit_cost {line.unit_cost} deviates "
                            f"{variance_pct:.2f}% from PO cost {po_line.unit_cost} "
                            f"(max allowed: {settings.max_price_variance_pct}%)"
                        ),
                        metadata={
                            "grn_cost": str(line.unit_cost),
                            "po_cost": str(po_line.unit_cost),
                            "variance_pct": str(variance_pct),
                        },
                    )

    # ── EXECUTION PASS ────────────────────────────────────────────────────
    receipt_movements = []
    for line in lines:
        product = _get_product(db, line.product_id, company_id)

        # Auto-create batch if needed
        batch_id = line.batch_id
        if product.is_batch_tracked and batch_id is None:
            batch = inv_service.create_batch(
                db,
                inv_schemas.BatchCreate(
                    product_id=line.product_id,
                    batch_number=line.batch_number,
                    expiry_date=line.expiry_date,
                ),
                company_id=company_id,
                actor_id=actor_id,
            )
            batch_id = batch.id
            line.batch_id = batch_id
            db.flush()

        base_qty = _to_base_qty(db, company_id, line.quantity_received, line.unit_id, product)
        base_cost = _to_base_unit_cost(db, company_id, line.unit_cost, line.unit_id, product)

        mv = inv_service.receive_stock(
            db,
            inv_schemas.ReceiveStockRequest(
                warehouse_id=line.warehouse_id,
                product_id=line.product_id,
                batch_id=batch_id,
                quantity=base_qty,
                unit_cost=base_cost,
                notes=f"GRN {grn.grn_number}",
            ),
            company_id=company_id,
            actor_id=actor_id,
        )
        line.stock_movement_id = mv.id
        receipt_movements.append(mv)
        db.flush()

        if line.po_line_id is not None:
            po_line = db.get(models.PurchaseOrderLine, line.po_line_id)
            if po_line is not None:
                po_line.quantity_received += line.quantity_received
                db.flush()
                _update_po_status(db, po_line.po_id)

    # Accounting: DR Inventory, CR GRN Accrual (atomic with stock receipt)
    from app.modules.accounting.integration import (
        PostingEvent, SourceModule, event_publisher, get_default_accounts,
    )
    defaults = get_default_accounts(db, company_id)
    if defaults is not None:
        receipt_cost = sum(mv.quantity * mv.unit_cost for mv in receipt_movements)
        if receipt_cost > 0:
            event_publisher.publish(db, PostingEvent(
                event_type="PURCHASE_GRN_POSTED",
                source_module=SourceModule.PURCHASING,
                payload={
                    "inventory_account":   defaults["inventory"],
                    "grn_accrual_account": defaults["grn_accrual"],
                    "receipt_cost":        str(receipt_cost),
                },
                entry_date=grn.receipt_date,
                company_id=company_id,
                actor_id=actor_id,
                idempotency_key=f"purchase_grn_{grn_id}_receipt",
                source_document=grn.grn_number,
            ))

    grn.status = models.GRNStatus.POSTED
    grn.updated_by = actor_id
    db.flush()
    return grn


def cancel_grn(
    db: Session,
    grn_id: int,
    company_id: int,
    actor_id: int | None = None,
    reason: str | None = None,
) -> models.GoodsReceipt:
    from app.modules.inventory import service as inv_service

    grn = get_grn(db, grn_id, company_id)

    if grn.status == models.GRNStatus.DRAFT:
        grn.status = models.GRNStatus.CANCELLED
        grn.updated_by = actor_id
        db.flush()
        return grn

    if grn.status != models.GRNStatus.POSTED:
        raise BusinessRuleViolation(f"Cannot cancel GRN with status {grn.status}")

    _require_approval(
        db,
        company_id=company_id,
        request_type=ApprovalRequestType.CANCEL_GRN,
        reference_type="goods_receipt",
        reference_id=grn_id,
        requested_by=actor_id,
        detail=f"Cancel posted GRN {grn.grn_number}",
        metadata={"reason": reason, "grn_number": grn.grn_number},
    )

    # Reverse all stock movements at original cost
    lines = _get_grn_lines(db, grn_id)
    for line in lines:
        if line.stock_movement_id is not None:
            inv_service.reverse_movement(
                db,
                line.stock_movement_id,
                company_id=company_id,
                actor_id=actor_id,
                notes=f"Cancellation of GRN {grn.grn_number}",
            )

    # Reverse the GRN accounting entry atomically
    import datetime as _dt
    from app.modules.accounting.integration import event_publisher as _ep
    _ep.reverse_document(
        db, f"purchase_grn_{grn_id}_receipt", _dt.date.today(), company_id, actor_id
    )

    grn.status = models.GRNStatus.CANCELLED
    grn.updated_by = actor_id
    db.flush()
    return grn


def get_grn(db: Session, grn_id: int, company_id: int) -> models.GoodsReceipt:
    grn = db.get(models.GoodsReceipt, grn_id)
    if grn is None or grn.company_id != company_id or grn.is_deleted:
        raise NotFoundError(f"GoodsReceipt {grn_id} not found")
    return grn


def get_grn_detail(
    db: Session, grn_id: int, company_id: int
) -> tuple[models.GoodsReceipt, list[models.GoodsReceiptLine]]:
    grn = get_grn(db, grn_id, company_id)
    return grn, _get_grn_lines(db, grn_id)


def list_grns(
    db: Session,
    company_id: int,
    supplier_id: int | None = None,
    status: models.GRNStatus | None = None,
) -> list[models.GoodsReceipt]:
    stmt = select(models.GoodsReceipt).where(
        models.GoodsReceipt.company_id == company_id,
        models.GoodsReceipt.is_deleted.is_(False),
    )
    if supplier_id is not None:
        stmt = stmt.where(models.GoodsReceipt.supplier_id == supplier_id)
    if status is not None:
        stmt = stmt.where(models.GoodsReceipt.status == status)
    return list(db.scalars(stmt.order_by(models.GoodsReceipt.id.desc())))


# ---------------------------------------------------------------------------
# SupplierInvoice
# ---------------------------------------------------------------------------


def create_supplier_invoice(
    db: Session,
    payload: schemas.SupplierInvoiceCreate,
    company_id: int,
    actor_id: int | None = None,
) -> models.SupplierInvoice:
    _get_branch(db, payload.branch_id, company_id)
    _get_supplier(db, payload.supplier_id, company_id)

    bill_number = _next_bill_number(db, company_id)
    bill = models.SupplierInvoice(
        company_id=company_id,
        branch_id=payload.branch_id,
        supplier_id=payload.supplier_id,
        goods_receipt_id=payload.goods_receipt_id,
        purchase_order_id=payload.purchase_order_id,
        bill_number=bill_number,
        supplier_ref=payload.supplier_ref,
        bill_date=payload.bill_date,
        status=models.BillStatus.DRAFT,
        grand_total=Decimal(0),
        amount_paid=Decimal(0),
        notes=payload.notes,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(bill)
    db.flush()

    total = Decimal(0)
    for lp in payload.lines:
        _get_product(db, lp.product_id, company_id)
        line_total = lp.quantity * lp.unit_cost + lp.cost_adjustment
        line = models.SupplierInvoiceLine(
            bill_id=bill.id,
            grn_line_id=lp.grn_line_id,
            product_id=lp.product_id,
            unit_id=lp.unit_id,
            quantity=lp.quantity,
            unit_cost=lp.unit_cost,
            cost_adjustment=lp.cost_adjustment,
            line_total=line_total,
            created_by=actor_id,
            updated_by=actor_id,
        )
        db.add(line)
        total += line_total
    db.flush()

    bill.grand_total = total
    db.flush()
    return bill


def post_supplier_invoice(
    db: Session,
    bill_id: int,
    company_id: int,
    actor_id: int | None = None,
) -> models.SupplierInvoice:
    bill = get_supplier_invoice(db, bill_id, company_id)
    if bill.status != models.BillStatus.DRAFT:
        raise BusinessRuleViolation(f"Cannot post bill with status {bill.status}")

    lines = _get_bill_lines(db, bill_id)
    if not lines:
        raise BusinessRuleViolation("Bill has no lines")

    settings = get_or_create_settings(db, company_id)

    # THREE_WAY_MATCH extension point
    if settings.purchase_flow_policy == models.PurchaseFlowPolicy.THREE_WAY_MATCH:
        raise BusinessRuleViolation(
            "THREE_WAY_MATCH is not yet implemented; switch policy to PO_REQUIRED or DIRECT_RECEIPT"
        )

    _check_backdated(db, company_id, bill.bill_date, "supplier_invoice", bill_id, actor_id)

    supplier = _get_supplier(db, bill.supplier_id, company_id)

    # Supplier credit limit check
    if supplier.credit_limit is not None and not settings.allow_supplier_over_credit_limit:
        exposure = _compute_supplier_exposure(db, supplier.id)
        if exposure + bill.grand_total > supplier.credit_limit:
            _require_approval(
                db,
                company_id=company_id,
                request_type=ApprovalRequestType.SUPPLIER_CREDIT_LIMIT_OVERRIDE,
                reference_type="supplier_invoice",
                reference_id=bill_id,
                requested_by=actor_id,
                detail=(
                    f"Supplier credit limit {supplier.credit_limit} exceeded: "
                    f"exposure={exposure}, bill={bill.grand_total}"
                ),
                metadata={
                    "credit_limit": str(supplier.credit_limit),
                    "current_exposure": str(exposure),
                    "bill_amount": str(bill.grand_total),
                },
            )

    today = datetime.date.today()
    bill.due_date = today + datetime.timedelta(days=supplier.payment_term_days)
    bill.status = models.BillStatus.POSTED
    bill.posted_at = datetime.datetime.now(datetime.UTC)
    bill.updated_by = actor_id
    db.flush()

    # Accounting: DR GRN Accrual, CR AP (clears receipt accrual against the bill)
    from app.modules.accounting.integration import (
        PostingEvent, SourceModule, event_publisher, get_default_accounts,
    )
    defaults = get_default_accounts(db, company_id)
    if defaults is not None:
        event_publisher.publish(db, PostingEvent(
            event_type="SUPPLIER_INVOICE_POSTED",
            source_module=SourceModule.PURCHASING,
            payload={
                "grn_accrual_account": defaults["grn_accrual"],
                "ap_account":          defaults["ap"],
                "total_amount":        str(bill.grand_total),
            },
            entry_date=bill.bill_date,
            company_id=company_id,
            actor_id=actor_id,
            idempotency_key=f"purchase_bill_{bill_id}",
            source_document=bill.bill_number,
        ))
    return bill


def cancel_supplier_invoice(
    db: Session,
    bill_id: int,
    company_id: int,
    actor_id: int | None = None,
    reason: str | None = None,
) -> models.SupplierInvoice:
    bill = get_supplier_invoice(db, bill_id, company_id)

    if bill.status == models.BillStatus.DRAFT:
        bill.status = models.BillStatus.CANCELLED
        bill.updated_by = actor_id
        db.flush()
        return bill

    if bill.status == models.BillStatus.PAID:
        raise BusinessRuleViolation("Cannot cancel a fully paid bill; reverse the payment first")

    if bill.status != models.BillStatus.POSTED:
        raise BusinessRuleViolation(f"Cannot cancel bill with status {bill.status}")

    _require_approval(
        db,
        company_id=company_id,
        request_type=ApprovalRequestType.CANCEL_SUPPLIER_INVOICE,
        reference_type="supplier_invoice",
        reference_id=bill_id,
        requested_by=actor_id,
        detail=f"Cancel posted bill {bill.bill_number}",
        metadata={"reason": reason, "bill_number": bill.bill_number},
    )

    # Reverse the bill accounting entry atomically
    import datetime as _dt
    from app.modules.accounting.integration import event_publisher as _ep
    _ep.reverse_document(
        db, f"purchase_bill_{bill_id}", _dt.date.today(), company_id, actor_id
    )

    bill.status = models.BillStatus.CANCELLED
    bill.updated_by = actor_id
    db.flush()
    return bill


def get_supplier_invoice(db: Session, bill_id: int, company_id: int) -> models.SupplierInvoice:
    bill = db.get(models.SupplierInvoice, bill_id)
    if bill is None or bill.company_id != company_id or bill.is_deleted:
        raise NotFoundError(f"SupplierInvoice {bill_id} not found")
    return bill


def get_supplier_invoice_detail(
    db: Session, bill_id: int, company_id: int
) -> tuple[models.SupplierInvoice, list[models.SupplierInvoiceLine]]:
    bill = get_supplier_invoice(db, bill_id, company_id)
    return bill, _get_bill_lines(db, bill_id)


def list_supplier_invoices(
    db: Session,
    company_id: int,
    supplier_id: int | None = None,
    status: models.BillStatus | None = None,
) -> list[models.SupplierInvoice]:
    stmt = select(models.SupplierInvoice).where(
        models.SupplierInvoice.company_id == company_id,
        models.SupplierInvoice.is_deleted.is_(False),
    )
    if supplier_id is not None:
        stmt = stmt.where(models.SupplierInvoice.supplier_id == supplier_id)
    if status is not None:
        stmt = stmt.where(models.SupplierInvoice.status == status)
    return list(db.scalars(stmt.order_by(models.SupplierInvoice.id.desc())))


# ---------------------------------------------------------------------------
# PurchaseReturn
# ---------------------------------------------------------------------------


def create_purchase_return(
    db: Session,
    payload: schemas.PurchaseReturnCreate,
    company_id: int,
    actor_id: int | None = None,
) -> models.PurchaseReturn:
    _get_branch(db, payload.branch_id, company_id)
    _get_supplier(db, payload.supplier_id, company_id)

    grn = get_grn(db, payload.original_grn_id, company_id)
    if grn.status != models.GRNStatus.POSTED:
        raise BusinessRuleViolation(
            f"Purchase returns can only be raised against POSTED GRNs (status: {grn.status})"
        )

    return_number = _next_return_number(db, company_id)
    ret = models.PurchaseReturn(
        company_id=company_id,
        branch_id=payload.branch_id,
        supplier_id=payload.supplier_id,
        original_grn_id=payload.original_grn_id,
        return_number=return_number,
        return_date=payload.return_date,
        status=models.ReturnStatus.DRAFT,
        reason=payload.reason,
        total=Decimal(0),
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(ret)
    db.flush()

    total = Decimal(0)
    for lp in payload.lines:
        grn_line = db.get(models.GoodsReceiptLine, lp.original_grn_line_id)
        if grn_line is None or grn_line.grn_id != grn.id or grn_line.is_deleted:
            raise NotFoundError(
                f"GoodsReceiptLine {lp.original_grn_line_id} not found on this GRN"
            )

        already_returned = _total_returned_for_grn_line(db, grn_line.id)
        returnable = grn_line.quantity_received - already_returned
        if lp.quantity_returned > returnable:
            raise BusinessRuleViolation(
                f"Cannot return {lp.quantity_returned}: "
                f"received={grn_line.quantity_received}, "
                f"already returned={already_returned}, "
                f"returnable={returnable}"
            )

        line_total = lp.quantity_returned * grn_line.unit_cost
        line = models.PurchaseReturnLine(
            return_id=ret.id,
            original_grn_line_id=grn_line.id,
            quantity_returned=lp.quantity_returned,
            line_total=line_total,
            created_by=actor_id,
            updated_by=actor_id,
        )
        db.add(line)
        total += line_total
    db.flush()

    ret.total = total
    db.flush()
    return ret


def post_purchase_return(
    db: Session,
    return_id: int,
    company_id: int,
    actor_id: int | None = None,
) -> models.PurchaseReturn:
    from app.modules.inventory import schemas as inv_schemas
    from app.modules.inventory import service as inv_service

    ret = get_purchase_return(db, return_id, company_id)
    if ret.status != models.ReturnStatus.DRAFT:
        raise BusinessRuleViolation(f"Cannot post return with status {ret.status}")

    lines = _get_return_lines(db, return_id)
    if not lines:
        raise BusinessRuleViolation("Purchase return has no lines")

    # ALWAYS requires approval (MVP policy; conditional triggers added here later)
    _require_approval(
        db,
        company_id=company_id,
        request_type=ApprovalRequestType.PURCHASE_RETURN,
        reference_type="purchase_return",
        reference_id=return_id,
        requested_by=actor_id,
        detail=f"Post purchase return {ret.return_number}",
        metadata={"return_number": ret.return_number},
    )

    # Approval granted — issue stock back to supplier
    return_movements = []
    for line in lines:
        grn_line = db.get(models.GoodsReceiptLine, line.original_grn_line_id)
        product = _get_product(db, grn_line.product_id, company_id)

        base_qty = _to_base_qty(
            db, company_id, line.quantity_returned, grn_line.unit_id, product
        )

        mv = inv_service.issue_stock(
            db,
            inv_schemas.IssueStockRequest(
                warehouse_id=grn_line.warehouse_id,
                product_id=grn_line.product_id,
                batch_id=grn_line.batch_id,
                quantity=base_qty,
                notes=f"Purchase return {ret.return_number}",
            ),
            company_id=company_id,
            actor_id=actor_id,
        )
        line.stock_movement_id = mv.id
        return_movements.append(mv)
        db.flush()

    # Accounting: DR GRN Accrual, CR Inventory (at cost stock left at)
    from app.modules.accounting.integration import (
        PostingEvent, SourceModule, event_publisher, get_default_accounts,
    )
    import datetime as _dt
    defaults = get_default_accounts(db, company_id)
    if defaults is not None:
        # issue movements carry negative quantity; negate to get a positive cost
        return_cost = sum(-mv.quantity * mv.unit_cost for mv in return_movements)
        if return_cost > 0:
            event_publisher.publish(db, PostingEvent(
                event_type="PURCHASE_RETURN_POSTED",
                source_module=SourceModule.PURCHASING,
                payload={
                    "grn_accrual_account": defaults["grn_accrual"],
                    "inventory_account":   defaults["inventory"],
                    "return_cost":         str(return_cost),
                },
                entry_date=ret.return_date,
                company_id=company_id,
                actor_id=actor_id,
                idempotency_key=f"purchase_return_{return_id}",
                source_document=ret.return_number,
            ))

    ret.status = models.ReturnStatus.POSTED
    ret.updated_by = actor_id
    db.flush()
    return ret


def get_purchase_return(
    db: Session, return_id: int, company_id: int
) -> models.PurchaseReturn:
    ret = db.get(models.PurchaseReturn, return_id)
    if ret is None or ret.company_id != company_id or ret.is_deleted:
        raise NotFoundError(f"PurchaseReturn {return_id} not found")
    return ret


def get_purchase_return_detail(
    db: Session, return_id: int, company_id: int
) -> tuple[models.PurchaseReturn, list[models.PurchaseReturnLine]]:
    ret = get_purchase_return(db, return_id, company_id)
    return ret, _get_return_lines(db, return_id)


def list_purchase_returns(
    db: Session,
    company_id: int,
    supplier_id: int | None = None,
) -> list[models.PurchaseReturn]:
    stmt = select(models.PurchaseReturn).where(
        models.PurchaseReturn.company_id == company_id,
        models.PurchaseReturn.is_deleted.is_(False),
    )
    if supplier_id is not None:
        stmt = stmt.where(models.PurchaseReturn.supplier_id == supplier_id)
    return list(db.scalars(stmt.order_by(models.PurchaseReturn.id.desc())))


# ---------------------------------------------------------------------------
# SupplierPayment
# ---------------------------------------------------------------------------


def create_supplier_payment(
    db: Session,
    payload: schemas.SupplierPaymentCreate,
    company_id: int,
    actor_id: int | None = None,
) -> models.SupplierPayment:
    _get_branch(db, payload.branch_id, company_id)
    _get_supplier(db, payload.supplier_id, company_id)

    payment_number = _next_payment_number(db, company_id)
    payment = models.SupplierPayment(
        company_id=company_id,
        branch_id=payload.branch_id,
        supplier_id=payload.supplier_id,
        payment_number=payment_number,
        payment_date=payload.payment_date,
        total_amount=payload.total_amount,
        allocation_method=payload.allocation_method,
        status=models.PaymentStatus.DRAFT,
        notes=payload.notes,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(payment)
    db.flush()

    if payload.allocation_method == models.PaymentAllocationMethod.MANUAL and payload.lines:
        for lp in payload.lines:
            bill = db.get(models.SupplierInvoice, lp.bill_id)
            if (
                bill is None
                or bill.supplier_id != payload.supplier_id
                or bill.company_id != company_id
            ):
                raise NotFoundError(f"SupplierInvoice {lp.bill_id} not found for this supplier")
            pl = models.SupplierPaymentLine(
                payment_id=payment.id,
                bill_id=lp.bill_id,
                amount_applied=lp.amount_applied,
                created_by=actor_id,
                updated_by=actor_id,
            )
            db.add(pl)
        db.flush()

    return payment


def post_supplier_payment(
    db: Session,
    payment_id: int,
    company_id: int,
    actor_id: int | None = None,
) -> models.SupplierPayment:
    payment = get_supplier_payment(db, payment_id, company_id)
    if payment.status != models.PaymentStatus.DRAFT:
        raise BusinessRuleViolation(f"Cannot post payment with status {payment.status}")

    if payment.allocation_method == models.PaymentAllocationMethod.AUTO:
        _auto_allocate_payment(db, payment, actor_id)
    else:
        _apply_manual_payment_allocations(db, payment, actor_id)

    # Accounting: DR AP, CR Cash
    from app.modules.accounting.integration import (
        PostingEvent, SourceModule, event_publisher, get_default_accounts,
    )
    defaults = get_default_accounts(db, company_id)
    if defaults is not None:
        event_publisher.publish(db, PostingEvent(
            event_type="SUPPLIER_PAYMENT_POSTED",
            source_module=SourceModule.PURCHASING,
            payload={
                "ap_account":   defaults["ap"],
                "cash_account": defaults["cash"],
                "total_amount": str(payment.total_amount),
            },
            entry_date=payment.payment_date,
            company_id=company_id,
            actor_id=actor_id,
            idempotency_key=f"purchase_payment_{payment_id}",
            source_document=payment.payment_number,
        ))

    payment.status = models.PaymentStatus.POSTED
    payment.updated_by = actor_id
    db.flush()
    return payment


def _auto_allocate_payment(
    db: Session, payment: models.SupplierPayment, actor_id: int | None
) -> None:
    stmt = (
        select(models.SupplierInvoice)
        .where(
            models.SupplierInvoice.supplier_id == payment.supplier_id,
            models.SupplierInvoice.company_id == payment.company_id,
            models.SupplierInvoice.status == models.BillStatus.POSTED,
            models.SupplierInvoice.is_deleted.is_(False),
        )
        .order_by(
            models.SupplierInvoice.due_date.nulls_last(),
            models.SupplierInvoice.id,
        )
    )
    bills = list(db.scalars(stmt))

    remaining = payment.total_amount
    for bill in bills:
        if remaining <= 0:
            break
        open_amount = bill.grand_total - bill.amount_paid
        if open_amount <= 0:
            continue
        apply = min(open_amount, remaining)
        pl = models.SupplierPaymentLine(
            payment_id=payment.id,
            bill_id=bill.id,
            amount_applied=apply,
            created_by=actor_id,
            updated_by=actor_id,
        )
        db.add(pl)
        bill.amount_paid += apply
        if bill.amount_paid >= bill.grand_total:
            bill.status = models.BillStatus.PAID
        bill.updated_by = actor_id
        db.flush()
        remaining -= apply


def _apply_manual_payment_allocations(
    db: Session, payment: models.SupplierPayment, actor_id: int | None
) -> None:
    stmt = select(models.SupplierPaymentLine).where(
        models.SupplierPaymentLine.payment_id == payment.id
    )
    lines = list(db.scalars(stmt))
    total_allocated = sum((ln.amount_applied for ln in lines), Decimal(0))
    if total_allocated > payment.total_amount:
        raise BusinessRuleViolation(
            f"Total allocated {total_allocated} exceeds payment amount {payment.total_amount}"
        )
    for ln in lines:
        bill = db.get(models.SupplierInvoice, ln.bill_id)
        if bill is None or bill.status not in (
            models.BillStatus.POSTED,
            models.BillStatus.PAID,
        ):
            raise BusinessRuleViolation(
                f"Bill {ln.bill_id} is not in a state that accepts payment"
            )
        open_amount = bill.grand_total - bill.amount_paid
        if ln.amount_applied > open_amount:
            raise BusinessRuleViolation(
                f"Cannot apply {ln.amount_applied} to bill {ln.bill_id}: "
                f"open balance is only {open_amount}"
            )
        bill.amount_paid += ln.amount_applied
        if bill.amount_paid >= bill.grand_total:
            bill.status = models.BillStatus.PAID
        bill.updated_by = actor_id
        db.flush()


def cancel_supplier_payment(
    db: Session,
    payment_id: int,
    company_id: int,
    actor_id: int | None = None,
) -> models.SupplierPayment:
    payment = get_supplier_payment(db, payment_id, company_id)

    if payment.status == models.PaymentStatus.CANCELLED:
        return payment

    if payment.status == models.PaymentStatus.POSTED:
        stmt = select(models.SupplierPaymentLine).where(
            models.SupplierPaymentLine.payment_id == payment_id
        )
        lines = list(db.scalars(stmt))
        for ln in lines:
            bill = db.get(models.SupplierInvoice, ln.bill_id)
            if bill is not None:
                bill.amount_paid -= ln.amount_applied
                if bill.status == models.BillStatus.PAID:
                    bill.status = models.BillStatus.POSTED
                bill.updated_by = actor_id
                db.flush()

        # Reverse payment accounting entry atomically
        import datetime as _dt
        from app.modules.accounting.integration import event_publisher as _ep
        _ep.reverse_document(
            db, f"purchase_payment_{payment_id}", _dt.date.today(), company_id, actor_id
        )

    payment.status = models.PaymentStatus.CANCELLED
    payment.updated_by = actor_id
    db.flush()
    return payment


def get_supplier_payment(
    db: Session, payment_id: int, company_id: int
) -> models.SupplierPayment:
    payment = db.get(models.SupplierPayment, payment_id)
    if payment is None or payment.company_id != company_id or payment.is_deleted:
        raise NotFoundError(f"SupplierPayment {payment_id} not found")
    return payment


def get_supplier_payment_detail(
    db: Session, payment_id: int, company_id: int
) -> tuple[models.SupplierPayment, list[models.SupplierPaymentLine]]:
    payment = get_supplier_payment(db, payment_id, company_id)
    stmt = select(models.SupplierPaymentLine).where(
        models.SupplierPaymentLine.payment_id == payment_id
    )
    lines = list(db.scalars(stmt))
    return payment, lines


def list_supplier_payments(
    db: Session,
    company_id: int,
    supplier_id: int | None = None,
) -> list[models.SupplierPayment]:
    stmt = select(models.SupplierPayment).where(
        models.SupplierPayment.company_id == company_id,
        models.SupplierPayment.is_deleted.is_(False),
    )
    if supplier_id is not None:
        stmt = stmt.where(models.SupplierPayment.supplier_id == supplier_id)
    return list(db.scalars(stmt.order_by(models.SupplierPayment.id.desc())))
