"""Sales module tests.

Covers: settings, price lists, ApprovalRequest framework, invoice CRUD,
post_invoice atomicity, cancel-after-post reversal, credit notes returning
to original batch, collections (FIFO + manual), unit-conversion precision.

All tests run in a rolled-back transaction — nothing persists.
"""

import datetime
from decimal import Decimal

import pytest

from app.core.exceptions import ApprovalRequired, BusinessRuleViolation, NotFoundError
from app.modules.auth import schemas as auth_schemas
from app.modules.auth import service as auth_service
from app.modules.inventory import schemas as inv_schemas
from app.modules.inventory import service as inv_service
from app.modules.master_data import schemas as md_schemas
from app.modules.master_data import service as md_service
from app.modules.master_data.models import CustomerType, PaymentTerms, ProductType, UnitType
from app.modules.organization import schemas as org_schemas
from app.modules.organization import service as org_service
from app.modules.organization.models import BranchType, WarehouseType
from app.modules.sales import schemas as s_schemas
from app.modules.sales import service as s_service
from app.modules.sales.models import (
    AllocationMethod,
    ApprovalRequestType,
    ApprovalStatus,
    CollectionStatus,
    CreditNoteStatus,
    InvoiceStatus,
)

# ---------------------------------------------------------------------------
# Low-level builder helpers
# ---------------------------------------------------------------------------


def _company(db, code="SALCO"):
    return org_service.create_company(
        db,
        org_schemas.CompanyCreate(
            code=code,
            name_en=f"{code} Ltd",
            name_ar=f"شركة {code}",
            commercial_registration_no=f"CR-{code}",
        ),
    )


def _branch(db, company_id, code="BR1"):
    return org_service.create_branch(
        db,
        org_schemas.BranchCreate(
            company_id=company_id,
            code=code,
            name_en=code,
            name_ar=code,
            branch_type=BranchType.BOTH,
        ),
    )


def _warehouse(db, branch_id, code="WH1"):
    return org_service.create_warehouse(
        db,
        org_schemas.WarehouseCreate(
            branch_id=branch_id,
            code=code,
            name_en=code,
            name_ar=code,
            warehouse_type=WarehouseType.FINISHED_GOODS,
        ),
    )


def _unit(db, company_id, code, utype=UnitType.WEIGHT):
    return md_service.create_unit(
        db,
        md_schemas.UnitOfMeasureCreate(
            code=code, name_en=code, name_ar=code, symbol=code[:3], unit_type=utype
        ),
        company_id=company_id,
    )


def _category(db, company_id, code="CAT"):
    return md_service.create_category(
        db,
        md_schemas.CategoryCreate(code=code, name_en=code, name_ar=code),
        company_id=company_id,
    )


def _product(db, company_id, cat_id, base_unit_id, code="PROD", sales_unit_id=None,
             batch_tracked=False):
    return md_service.create_product(
        db,
        md_schemas.ProductCreate(
            code=code,
            name_en=code,
            name_ar=code,
            category_id=cat_id,
            product_type=ProductType.FINISHED_GOOD,
            base_unit_id=base_unit_id,
            sales_unit_id=sales_unit_id,
            is_batch_tracked=batch_tracked,
        ),
        company_id=company_id,
    )


def _customer(db, company_id, code="CUST", terms=PaymentTerms.CASH,
              credit_limit=None, term_days=30):
    return md_service.create_customer(
        db,
        md_schemas.CustomerCreate(
            code=code,
            name_en=code,
            name_ar=code,
            customer_type=CustomerType.SHOP,
            payment_terms=terms,
            credit_limit=credit_limit,
            payment_term_days=term_days,
        ),
        company_id=company_id,
    )


def _conversion(db, company_id, from_id, to_id, factor, product_id=None):
    return md_service.create_conversion(
        db,
        md_schemas.UnitConversionCreate(
            from_unit_id=from_id, to_unit_id=to_id, factor=Decimal(str(factor)),
            product_id=product_id
        ),
        company_id=company_id,
    )


def _batch(db, company_id, product_id, number="B001"):
    return inv_service.create_batch(
        db,
        inv_schemas.BatchCreate(
            product_id=product_id,
            batch_number=number,
            expiry_date=datetime.date.today() + datetime.timedelta(days=90),
        ),
        company_id=company_id,
    )


def _recv(db, cid, wid, pid, qty, cost, batch_id=None):
    return inv_service.receive_stock(
        db,
        inv_schemas.ReceiveStockRequest(
            warehouse_id=wid, product_id=pid, batch_id=batch_id,
            quantity=Decimal(str(qty)), unit_cost=Decimal(str(cost)),
        ),
        company_id=cid,
    )


def _user(db, company_id, username="user1"):
    return auth_service.create_user(
        db,
        auth_schemas.UserCreate(
            username=username,
            email=f"{username}@test.com",
            full_name_en=username,
            full_name_ar=username,
            password="Password123!",
        ),
        company_id=company_id,
    )


def _price_list(db, company_id, code="STD"):
    return s_service.create_price_list(
        db,
        s_schemas.PriceListCreate(
            code=code, name_en=code, name_ar=code, is_default=True
        ),
        company_id=company_id,
    )


def _add_item(db, pl_id, product_id, price, company_id):
    return s_service.add_price_list_item(
        db, pl_id,
        s_schemas.PriceListItemCreate(product_id=product_id, unit_price=Decimal(str(price))),
        company_id=company_id,
    )


def _create_inv(db, company_id, branch_id, customer_id, pl_id, lines, inv_date=None):
    return s_service.create_invoice(
        db,
        s_schemas.SalesInvoiceCreate(
            branch_id=branch_id,
            customer_id=customer_id,
            price_list_id=pl_id,
            invoice_date=inv_date or datetime.date.today(),
            lines=lines,
        ),
        company_id=company_id,
    )


def _line(product_id, warehouse_id, unit_id, qty, price,
          batch_id=None, price_source="PRICE_LIST", discount=0):
    return s_schemas.InvoiceLineCreate(
        product_id=product_id,
        warehouse_id=warehouse_id,
        batch_id=batch_id,
        unit_id=unit_id,
        quantity_ordered=Decimal(str(qty)),
        unit_price=Decimal(str(price)),
        price_source=price_source,
        line_discount=Decimal(str(discount)),
    )


# ---------------------------------------------------------------------------
# Shared fixture: a fully-wired world in one company
# ---------------------------------------------------------------------------


@pytest.fixture()
def world(db_session):
    """Returns a namespace with all test fixtures pre-created."""
    db = db_session
    co = _company(db)
    br = _branch(db, co.id)
    wh = _warehouse(db, br.id)
    wh2 = _warehouse(db, br.id, code="WH2")

    gram = _unit(db, co.id, "G", UnitType.WEIGHT)
    kg = _unit(db, co.id, "KG", UnitType.WEIGHT)
    piece = _unit(db, co.id, "PC", UnitType.COUNT)
    ctn = _unit(db, co.id, "CTN", UnitType.COUNT)

    _conversion(db, co.id, kg.id, gram.id, "1000")
    _conversion(db, co.id, ctn.id, piece.id, "24", product_id=None)

    cat = _category(db, co.id)
    prod = _product(db, co.id, cat.id, gram.id, "PROD", sales_unit_id=kg.id)
    bp = _product(db, co.id, cat.id, gram.id, "BPROD", sales_unit_id=kg.id, batch_tracked=True)
    cnt_prod = _product(db, co.id, cat.id, piece.id, "CNTPROD")

    batch = _batch(db, co.id, bp.id)

    cash_cust = _customer(db, co.id, "CASH-C", PaymentTerms.CASH)
    cred_cust = _customer(db, co.id, "CRED-C", PaymentTerms.CREDIT,
                          credit_limit=Decimal("100"), term_days=30)

    pl = _price_list(db, co.id)
    _add_item(db, pl.id, prod.id, "10.000", co.id)
    _add_item(db, pl.id, bp.id, "10.000", co.id)
    _add_item(db, pl.id, cnt_prod.id, "5.000", co.id)

    # Put stock in WH: 50 KG of prod (non-batch), 30 KG of bp (batch), 100 pcs cnt_prod
    _recv(db, co.id, wh.id, prod.id, 50000, "0.005")           # 50 kg in grams
    _recv(db, co.id, wh.id, bp.id, 30000, "0.005", batch.id)   # 30 kg in grams
    _recv(db, co.id, wh.id, cnt_prod.id, 100, "3.000")

    # Two users for maker-checker approval tests
    actor = _user(db, co.id, "actor")
    approver = _user(db, co.id, "approver")

    from types import SimpleNamespace
    return SimpleNamespace(
        company=co,
        branch=br,
        warehouse=wh,
        warehouse2=wh2,
        gram_unit=gram,
        kg_unit=kg,
        piece_unit=piece,
        ctn_unit=ctn,
        product=prod,
        batch_product=bp,
        cnt_product=cnt_prod,
        batch=batch,
        cash_customer=cash_cust,
        credit_customer=cred_cust,
        price_list=pl,
        actor=actor,
        approver=approver,
    )


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def test_settings_get_or_create(db_session):
    db = db_session
    co = _company(db)
    s = s_service.get_or_create_settings(db, co.id)
    assert s.company_id == co.id
    assert s.allow_sale_over_credit_limit is False
    # Second call returns the same row
    s2 = s_service.get_or_create_settings(db, co.id)
    assert s2.id == s.id


def test_settings_update(db_session):
    db = db_session
    co = _company(db)
    s = s_service.update_settings(
        db,
        s_schemas.SalesSettingsUpdate(allow_backdated_invoice=True),
        company_id=co.id,
    )
    assert s.allow_backdated_invoice is True


# ---------------------------------------------------------------------------
# Price Lists
# ---------------------------------------------------------------------------


def test_price_list_create_and_default_unique(db_session, world):
    db = db_session
    pl2 = s_service.create_price_list(
        db,
        s_schemas.PriceListCreate(
            code="PL2", name_en="PL2", name_ar="PL2", is_default=True
        ),
        company_id=world.company.id,
    )
    # Existing default should now be cleared
    db.refresh(world.price_list)
    assert world.price_list.is_default is False
    assert pl2.is_default is True


def test_price_list_item_add_and_list(db_session, world):
    db = db_session
    items = s_service.list_price_list_items(db, world.price_list.id, world.company.id)
    assert len(items) == 3  # prod, bp, cnt_prod seeded in world


def test_price_list_item_update(db_session, world):
    db = db_session
    items = s_service.list_price_list_items(db, world.price_list.id, world.company.id)
    item = items[0]
    updated = s_service.update_price_list_item(
        db, item.id, s_schemas.PriceListItemUpdate(unit_price=Decimal("15.000")),
        company_id=world.company.id,
    )
    assert updated.unit_price == Decimal("15.000")


# ---------------------------------------------------------------------------
# Invoice creation
# ---------------------------------------------------------------------------


def test_create_invoice_draft(db_session, world):
    db = db_session
    w = world
    inv = _create_inv(
        db, w.company.id, w.branch.id, w.cash_customer.id, w.price_list.id,
        [_line(w.product.id, w.warehouse.id, w.kg_unit.id, 5, "10.000")]
    )
    assert inv.status == InvoiceStatus.DRAFT
    assert inv.invoice_number.startswith("INV-")
    assert inv.grand_total == Decimal("50.000")
    assert inv.payment_terms_type == "CASH"


def test_create_invoice_number_increments(db_session, world):
    db = db_session
    w = world
    inv1 = _create_inv(
        db, w.company.id, w.branch.id, w.cash_customer.id, w.price_list.id,
        [_line(w.product.id, w.warehouse.id, w.kg_unit.id, 1, "10.000")]
    )
    inv2 = _create_inv(
        db, w.company.id, w.branch.id, w.cash_customer.id, w.price_list.id,
        [_line(w.product.id, w.warehouse.id, w.kg_unit.id, 1, "10.000")]
    )
    assert inv1.invoice_number != inv2.invoice_number


def test_create_invoice_inactive_customer_blocked(db_session, world):
    db = db_session
    w = world
    w.cash_customer.is_active = False
    db.flush()
    with pytest.raises(BusinessRuleViolation, match="inactive"):
        _create_inv(
            db, w.company.id, w.branch.id, w.cash_customer.id, w.price_list.id,
            [_line(w.product.id, w.warehouse.id, w.kg_unit.id, 1, "10.000")]
        )


def test_create_invoice_inactive_customer_allowed_by_setting(db_session, world):
    db = db_session
    w = world
    w.cash_customer.is_active = False
    db.flush()
    s_service.update_settings(
        db,
        s_schemas.SalesSettingsUpdate(allow_sale_to_inactive_customer=True),
        company_id=w.company.id,
    )
    inv = _create_inv(
        db, w.company.id, w.branch.id, w.cash_customer.id, w.price_list.id,
        [_line(w.product.id, w.warehouse.id, w.kg_unit.id, 1, "10.000")]
    )
    assert inv.status == InvoiceStatus.DRAFT


def test_create_invoice_no_price_list_entry_raises(db_session, world):
    db = db_session
    w = world
    cat2 = _category(db, w.company.id, "C2")
    new_prod = _product(db, w.company.id, cat2.id, w.gram_unit.id, "NOPRICE")
    with pytest.raises(BusinessRuleViolation, match="no price"):
        _create_inv(
            db, w.company.id, w.branch.id, w.cash_customer.id, w.price_list.id,
            [_line(new_prod.id, w.warehouse.id, w.kg_unit.id, 1, "10.000")]
        )


def test_create_invoice_manual_price_no_list_entry(db_session, world):
    db = db_session
    w = world
    cat2 = _category(db, w.company.id, "CAT2")
    new_prod = _product(db, w.company.id, cat2.id, w.gram_unit.id, "NOPRICE2")
    _recv(db, w.company.id, w.warehouse.id, new_prod.id, 1000, "1.000")
    inv = _create_inv(
        db, w.company.id, w.branch.id, w.cash_customer.id, w.price_list.id,
        [_line(new_prod.id, w.warehouse.id, w.gram_unit.id, 100, "2.000",
               price_source="MANUAL")]
    )
    assert inv.status == InvoiceStatus.DRAFT


# ---------------------------------------------------------------------------
# post_invoice: unit conversion — the critical E test
# ---------------------------------------------------------------------------


def test_post_invoice_unit_conversion_exact_base_qty(db_session, world):
    """Selling 2 cartons of a COUNT product that is 24 pcs/carton must issue
    exactly 48 base pieces — zero rounding drift allowed."""
    db = db_session
    w = world
    # cnt_prod: base_unit=piece; universal conversion CTN->PC = 24
    # Put 100 pcs in stock (already done in world fixture)
    qty_before = inv_service._get_balance(
        db, w.company.id, w.warehouse.id, w.cnt_product.id, None
    ).quantity_on_hand
    assert qty_before == Decimal("100")

    inv = _create_inv(
        db, w.company.id, w.branch.id, w.cash_customer.id, w.price_list.id,
        [_line(w.cnt_product.id, w.warehouse.id, w.ctn_unit.id, 2, "5.000")]
    )
    s_service.post_invoice(db, inv.id, company_id=w.company.id)

    qty_after = inv_service._get_balance(
        db, w.company.id, w.warehouse.id, w.cnt_product.id, None
    ).quantity_on_hand
    # 2 cartons * 24 pcs/carton = 48 pcs issued
    assert qty_after == Decimal("52"), (
        f"Expected 52 pcs remaining, got {qty_after} — unit conversion drift detected"
    )


# ---------------------------------------------------------------------------
# post_invoice: weight-unit conversion
# ---------------------------------------------------------------------------


def test_post_invoice_kg_to_gram_conversion(db_session, world):
    """Selling 5 KG of a product with base_unit=gram must issue exactly 5000 g."""
    db = db_session
    w = world
    qty_before = inv_service._get_balance(
        db, w.company.id, w.warehouse.id, w.product.id, None
    ).quantity_on_hand
    assert qty_before == Decimal("50000")  # 50 kg in grams

    inv = _create_inv(
        db, w.company.id, w.branch.id, w.cash_customer.id, w.price_list.id,
        [_line(w.product.id, w.warehouse.id, w.kg_unit.id, 5, "10.000")]
    )
    s_service.post_invoice(db, inv.id, company_id=w.company.id)

    qty_after = inv_service._get_balance(
        db, w.company.id, w.warehouse.id, w.product.id, None
    ).quantity_on_hand
    assert qty_after == Decimal("45000")  # 50000 - 5000


# ---------------------------------------------------------------------------
# post_invoice: due_date computation
# ---------------------------------------------------------------------------


def test_post_invoice_cash_due_date_equals_posted_date(db_session, world):
    db = db_session
    w = world
    inv = _create_inv(
        db, w.company.id, w.branch.id, w.cash_customer.id, w.price_list.id,
        [_line(w.product.id, w.warehouse.id, w.kg_unit.id, 1, "10.000")]
    )
    s_service.post_invoice(db, inv.id, company_id=w.company.id)
    db.refresh(inv)
    assert inv.due_date == datetime.date.today()
    assert inv.status == InvoiceStatus.POSTED


def test_post_invoice_credit_due_date_offset(db_session, world):
    db = db_session
    w = world
    inv = _create_inv(
        db, w.company.id, w.branch.id, w.credit_customer.id, w.price_list.id,
        [_line(w.product.id, w.warehouse.id, w.kg_unit.id, 1, "10.000")]
    )
    s_service.post_invoice(db, inv.id, company_id=w.company.id)
    db.refresh(inv)
    expected_due = datetime.date.today() + datetime.timedelta(days=30)
    assert inv.due_date == expected_due


# ---------------------------------------------------------------------------
# post_invoice: stock linkage + batch tracking
# ---------------------------------------------------------------------------


def test_post_invoice_links_stock_movement(db_session, world):
    db = db_session
    w = world
    inv = _create_inv(
        db, w.company.id, w.branch.id, w.cash_customer.id, w.price_list.id,
        [_line(w.batch_product.id, w.warehouse.id, w.kg_unit.id, 2, "10.000",
               batch_id=w.batch.id)]
    )
    s_service.post_invoice(db, inv.id, company_id=w.company.id)

    from app.modules.sales.models import SalesInvoiceLine
    from sqlalchemy import select
    lines = list(
        db.scalars(
            select(SalesInvoiceLine).where(SalesInvoiceLine.invoice_id == inv.id)
        )
    )
    assert all(ln.stock_movement_id is not None for ln in lines)


def test_post_invoice_reduces_batch_stock(db_session, world):
    db = db_session
    w = world
    qty_before = inv_service._get_balance(
        db, w.company.id, w.warehouse.id, w.batch_product.id, w.batch.id
    ).quantity_on_hand
    inv = _create_inv(
        db, w.company.id, w.branch.id, w.cash_customer.id, w.price_list.id,
        [_line(w.batch_product.id, w.warehouse.id, w.kg_unit.id, 5, "10.000",
               batch_id=w.batch.id)]
    )
    s_service.post_invoice(db, inv.id, company_id=w.company.id)
    qty_after = inv_service._get_balance(
        db, w.company.id, w.warehouse.id, w.batch_product.id, w.batch.id
    ).quantity_on_hand
    # 5 KG sold = 5000 g issued
    assert qty_after == qty_before - Decimal("5000")


def test_post_invoice_insufficient_stock_blocked(db_session, world):
    db = db_session
    w = world
    # Try to sell 60 KG when only 50 KG available (50000 g)
    inv = _create_inv(
        db, w.company.id, w.branch.id, w.cash_customer.id, w.price_list.id,
        [_line(w.product.id, w.warehouse.id, w.kg_unit.id, 60, "10.000")]
    )
    with pytest.raises(BusinessRuleViolation, match="[Ii]nsufficient"):
        s_service.post_invoice(db, inv.id, company_id=w.company.id)


def test_post_invoice_cannot_repost(db_session, world):
    db = db_session
    w = world
    inv = _create_inv(
        db, w.company.id, w.branch.id, w.cash_customer.id, w.price_list.id,
        [_line(w.product.id, w.warehouse.id, w.kg_unit.id, 1, "10.000")]
    )
    s_service.post_invoice(db, inv.id, company_id=w.company.id)
    with pytest.raises(BusinessRuleViolation, match="[Cc]annot post"):
        s_service.post_invoice(db, inv.id, company_id=w.company.id)


# ---------------------------------------------------------------------------
# Approval framework: credit limit
# ---------------------------------------------------------------------------


def test_post_invoice_credit_limit_triggers_approval(db_session, world):
    db = db_session
    w = world
    # credit_customer has credit_limit=100; invoice grand_total=200 → exceeds
    inv = _create_inv(
        db, w.company.id, w.branch.id, w.credit_customer.id, w.price_list.id,
        [_line(w.product.id, w.warehouse.id, w.kg_unit.id, 20, "10.000")]  # 200 KWD
    )
    with pytest.raises(ApprovalRequired) as exc_info:
        s_service.post_invoice(db, inv.id, company_id=w.company.id, actor_id=w.actor.id)
    req_id = exc_info.value.approval_request_id
    assert req_id is not None

    # Re-call raises ApprovalRequired again (existing PENDING)
    with pytest.raises(ApprovalRequired):
        s_service.post_invoice(db, inv.id, company_id=w.company.id, actor_id=w.actor.id)

    # Approve as a different user (maker-checker)
    s_service.approve_request(db, req_id, company_id=w.company.id, actor_id=w.approver.id)

    # Now posting succeeds
    s_service.post_invoice(db, inv.id, company_id=w.company.id, actor_id=w.actor.id)
    db.refresh(inv)
    assert inv.status == InvoiceStatus.POSTED


def test_approve_own_request_blocked(db_session, world):
    db = db_session
    w = world
    inv = _create_inv(
        db, w.company.id, w.branch.id, w.credit_customer.id, w.price_list.id,
        [_line(w.product.id, w.warehouse.id, w.kg_unit.id, 20, "10.000")]
    )
    with pytest.raises(ApprovalRequired) as exc_info:
        s_service.post_invoice(db, inv.id, company_id=w.company.id, actor_id=w.actor.id)
    req_id = exc_info.value.approval_request_id

    with pytest.raises(BusinessRuleViolation, match="maker-checker"):
        s_service.approve_request(db, req_id, company_id=w.company.id, actor_id=w.actor.id)


def test_rejected_approval_blocks_posting(db_session, world):
    db = db_session
    w = world
    inv = _create_inv(
        db, w.company.id, w.branch.id, w.credit_customer.id, w.price_list.id,
        [_line(w.product.id, w.warehouse.id, w.kg_unit.id, 20, "10.000")]
    )
    with pytest.raises(ApprovalRequired) as exc_info:
        s_service.post_invoice(db, inv.id, company_id=w.company.id, actor_id=w.actor.id)
    req_id = exc_info.value.approval_request_id

    s_service.reject_request(db, req_id, company_id=w.company.id, actor_id=w.approver.id, reason="No credit")

    with pytest.raises(BusinessRuleViolation, match="[Rr]ejected"):
        s_service.post_invoice(db, inv.id, company_id=w.company.id, actor_id=w.actor.id)


# ---------------------------------------------------------------------------
# Approval framework: backdated invoice
# ---------------------------------------------------------------------------


def test_backdated_invoice_triggers_approval(db_session, world):
    db = db_session
    w = world
    past_date = datetime.date.today() - datetime.timedelta(days=5)
    inv = _create_inv(
        db, w.company.id, w.branch.id, w.cash_customer.id, w.price_list.id,
        [_line(w.product.id, w.warehouse.id, w.kg_unit.id, 1, "10.000")],
        inv_date=past_date,
    )
    with pytest.raises(ApprovalRequired):
        s_service.post_invoice(db, inv.id, company_id=w.company.id, actor_id=w.actor.id)


def test_backdated_invoice_allowed_by_setting(db_session, world):
    db = db_session
    w = world
    s_service.update_settings(
        db, s_schemas.SalesSettingsUpdate(allow_backdated_invoice=True), company_id=w.company.id
    )
    past_date = datetime.date.today() - datetime.timedelta(days=5)
    inv = _create_inv(
        db, w.company.id, w.branch.id, w.cash_customer.id, w.price_list.id,
        [_line(w.product.id, w.warehouse.id, w.kg_unit.id, 1, "10.000")],
        inv_date=past_date,
    )
    s_service.post_invoice(db, inv.id, company_id=w.company.id)
    db.refresh(inv)
    assert inv.status == InvoiceStatus.POSTED


# ---------------------------------------------------------------------------
# Approval framework: manual price
# ---------------------------------------------------------------------------


def test_manual_price_triggers_approval_on_post(db_session, world):
    db = db_session
    w = world
    cat2 = _category(db, w.company.id, "CAT-MP")
    new_prod = _product(db, w.company.id, cat2.id, w.gram_unit.id, "MPPROD")
    _recv(db, w.company.id, w.warehouse.id, new_prod.id, 5000, "1.000")
    inv = _create_inv(
        db, w.company.id, w.branch.id, w.cash_customer.id, w.price_list.id,
        [_line(new_prod.id, w.warehouse.id, w.gram_unit.id, 100, "2.000",
               price_source="MANUAL")]
    )
    with pytest.raises(ApprovalRequired):
        s_service.post_invoice(db, inv.id, company_id=w.company.id, actor_id=w.actor.id)


# ---------------------------------------------------------------------------
# cancel_invoice
# ---------------------------------------------------------------------------


def test_cancel_draft_invoice(db_session, world):
    db = db_session
    w = world
    inv = _create_inv(
        db, w.company.id, w.branch.id, w.cash_customer.id, w.price_list.id,
        [_line(w.product.id, w.warehouse.id, w.kg_unit.id, 1, "10.000")]
    )
    s_service.cancel_invoice(db, inv.id, company_id=w.company.id)
    db.refresh(inv)
    assert inv.status == InvoiceStatus.CANCELLED


def test_cancel_posted_invoice_requires_approval(db_session, world):
    db = db_session
    w = world
    inv = _create_inv(
        db, w.company.id, w.branch.id, w.cash_customer.id, w.price_list.id,
        [_line(w.product.id, w.warehouse.id, w.kg_unit.id, 2, "10.000")]
    )
    s_service.post_invoice(db, inv.id, company_id=w.company.id)

    with pytest.raises(ApprovalRequired) as exc_info:
        s_service.cancel_invoice(db, inv.id, company_id=w.company.id, actor_id=w.actor.id)
    req_id = exc_info.value.approval_request_id

    s_service.approve_request(db, req_id, company_id=w.company.id, actor_id=w.approver.id)
    s_service.cancel_invoice(db, inv.id, company_id=w.company.id, actor_id=w.actor.id)

    db.refresh(inv)
    assert inv.status == InvoiceStatus.CANCELLED


def test_cancel_posted_invoice_reverses_stock(db_session, world):
    """Cancelling a posted invoice must return stock to original levels."""
    db = db_session
    w = world
    qty_before = inv_service._get_balance(
        db, w.company.id, w.warehouse.id, w.product.id, None
    ).quantity_on_hand
    inv = _create_inv(
        db, w.company.id, w.branch.id, w.cash_customer.id, w.price_list.id,
        [_line(w.product.id, w.warehouse.id, w.kg_unit.id, 5, "10.000")]
    )
    s_service.post_invoice(db, inv.id, company_id=w.company.id)

    # Approve cancellation
    with pytest.raises(ApprovalRequired) as exc_info:
        s_service.cancel_invoice(db, inv.id, company_id=w.company.id, actor_id=w.actor.id)
    s_service.approve_request(
        db, exc_info.value.approval_request_id, company_id=w.company.id, actor_id=w.approver.id
    )
    s_service.cancel_invoice(db, inv.id, company_id=w.company.id, actor_id=w.actor.id)

    qty_after = inv_service._get_balance(
        db, w.company.id, w.warehouse.id, w.product.id, None
    ).quantity_on_hand
    assert qty_after == qty_before


def test_cancel_posted_invoice_reverses_batch_stock(db_session, world):
    """Cancel-after-post returns stock to original batch exactly."""
    db = db_session
    w = world
    qty_before = inv_service._get_balance(
        db, w.company.id, w.warehouse.id, w.batch_product.id, w.batch.id
    ).quantity_on_hand
    inv = _create_inv(
        db, w.company.id, w.branch.id, w.cash_customer.id, w.price_list.id,
        [_line(w.batch_product.id, w.warehouse.id, w.kg_unit.id, 3, "10.000",
               batch_id=w.batch.id)]
    )
    s_service.post_invoice(db, inv.id, company_id=w.company.id)
    with pytest.raises(ApprovalRequired) as exc_info:
        s_service.cancel_invoice(db, inv.id, company_id=w.company.id, actor_id=w.actor.id)
    s_service.approve_request(
        db, exc_info.value.approval_request_id, company_id=w.company.id, actor_id=w.approver.id
    )
    s_service.cancel_invoice(db, inv.id, company_id=w.company.id, actor_id=w.actor.id)
    qty_after = inv_service._get_balance(
        db, w.company.id, w.warehouse.id, w.batch_product.id, w.batch.id
    ).quantity_on_hand
    assert qty_after == qty_before


# ---------------------------------------------------------------------------
# Credit Notes
# ---------------------------------------------------------------------------


@pytest.fixture()
def posted_invoice(db_session, world):
    """A POSTED invoice of 5 KG of batch_product."""
    db = db_session
    w = world
    inv = _create_inv(
        db, w.company.id, w.branch.id, w.cash_customer.id, w.price_list.id,
        [_line(w.batch_product.id, w.warehouse.id, w.kg_unit.id, 5, "10.000",
               batch_id=w.batch.id)]
    )
    s_service.post_invoice(db, inv.id, company_id=w.company.id)
    db.refresh(inv)
    return inv


def _first_line(db, invoice_id):
    from app.modules.sales.models import SalesInvoiceLine
    from sqlalchemy import select
    return db.scalars(
        select(SalesInvoiceLine).where(SalesInvoiceLine.invoice_id == invoice_id)
    ).first()


def test_create_credit_note(db_session, world, posted_invoice):
    db = db_session
    w = world
    inv = posted_invoice
    line = _first_line(db, inv.id)
    cn = s_service.create_credit_note(
        db,
        s_schemas.CreditNoteCreate(
            original_invoice_id=inv.id,
            credit_note_date=datetime.date.today(),
            reason="Test return",
            lines=[s_schemas.CreditNoteLineCreate(
                original_line_id=line.id, quantity_returned=Decimal("2")
            )],
        ),
        company_id=w.company.id,
    )
    assert cn.status == CreditNoteStatus.DRAFT
    assert cn.credit_note_number.startswith("CN-")
    assert cn.total == Decimal("20.000")  # 2 KG * 10 KWD/KG


def test_post_credit_note_returns_stock_to_original_batch(db_session, world, posted_invoice):
    """Posting a credit note must put stock back into the SAME batch."""
    db = db_session
    w = world
    inv = posted_invoice

    qty_after_sale = inv_service._get_balance(
        db, w.company.id, w.warehouse.id, w.batch_product.id, w.batch.id
    ).quantity_on_hand
    line = _first_line(db, inv.id)

    cn = s_service.create_credit_note(
        db,
        s_schemas.CreditNoteCreate(
            original_invoice_id=inv.id,
            credit_note_date=datetime.date.today(),
            lines=[s_schemas.CreditNoteLineCreate(
                original_line_id=line.id, quantity_returned=Decimal("2")
            )],
        ),
        company_id=w.company.id,
    )
    s_service.post_credit_note(db, cn.id, company_id=w.company.id)

    qty_after_return = inv_service._get_balance(
        db, w.company.id, w.warehouse.id, w.batch_product.id, w.batch.id
    ).quantity_on_hand
    # 2 KG (2000 g) returned to the original batch
    assert qty_after_return == qty_after_sale + Decimal("2000")
    db.refresh(cn)
    assert cn.status == CreditNoteStatus.POSTED


def test_credit_note_returnable_quantity_guard(db_session, world, posted_invoice):
    """Cannot return more than what was delivered."""
    db = db_session
    w = world
    inv = posted_invoice
    line = _first_line(db, inv.id)
    with pytest.raises(BusinessRuleViolation, match="[Cc]annot return"):
        s_service.create_credit_note(
            db,
            s_schemas.CreditNoteCreate(
                original_invoice_id=inv.id,
                credit_note_date=datetime.date.today(),
                lines=[s_schemas.CreditNoteLineCreate(
                    original_line_id=line.id, quantity_returned=Decimal("99")
                )],
            ),
            company_id=w.company.id,
        )


def test_credit_note_against_non_posted_invoice_blocked(db_session, world):
    db = db_session
    w = world
    inv = _create_inv(
        db, w.company.id, w.branch.id, w.cash_customer.id, w.price_list.id,
        [_line(w.product.id, w.warehouse.id, w.kg_unit.id, 1, "10.000")]
    )
    from sqlalchemy import select
    from app.modules.sales.models import SalesInvoiceLine
    line = db.scalars(
        select(SalesInvoiceLine).where(SalesInvoiceLine.invoice_id == inv.id)
    ).first()
    with pytest.raises(BusinessRuleViolation, match="POSTED"):
        s_service.create_credit_note(
            db,
            s_schemas.CreditNoteCreate(
                original_invoice_id=inv.id,
                credit_note_date=datetime.date.today(),
                lines=[s_schemas.CreditNoteLineCreate(
                    original_line_id=line.id, quantity_returned=Decimal("1")
                )],
            ),
            company_id=w.company.id,
        )


# ---------------------------------------------------------------------------
# Collections — FIFO auto-allocation
# ---------------------------------------------------------------------------


def _post_inv(db, world, customer, qty=5, price="10.000"):
    inv = _create_inv(
        db, world.company.id, world.branch.id, customer.id, world.price_list.id,
        [_line(world.product.id, world.warehouse.id, world.kg_unit.id, qty, price)]
    )
    s_service.post_invoice(db, inv.id, company_id=world.company.id)
    db.refresh(inv)
    return inv


def test_collection_fifo_allocates_oldest_first(db_session, world):
    db = db_session
    w = world
    # FIFO: both invoices are CASH (due_date = today), tiebreak by id (creation order)
    # inv1 is created first → lower id → FIFO picks it first
    inv1 = _post_inv(db, w, w.cash_customer, qty=5)   # 50 KWD
    inv2 = _post_inv(db, w, w.cash_customer, qty=3)   # 30 KWD

    col = s_service.create_collection(
        db,
        s_schemas.CollectionCreate(
            branch_id=w.branch.id,
            customer_id=w.cash_customer.id,
            collection_date=datetime.date.today(),
            total_amount=Decimal("60"),
            allocation_method=AllocationMethod.AUTO,
        ),
        company_id=w.company.id,
    )
    s_service.post_collection(db, col.id, company_id=w.company.id)
    db.refresh(inv1)
    db.refresh(inv2)
    # 50 applied to inv1 (fully collected), 10 to inv2 (partial)
    assert inv1.amount_collected == Decimal("50.000")
    assert inv1.status == InvoiceStatus.COLLECTED
    assert inv2.amount_collected == Decimal("10.000")
    assert inv2.status == InvoiceStatus.POSTED  # still open


def test_collection_marks_fully_paid_invoice_collected(db_session, world):
    db = db_session
    w = world
    inv = _post_inv(db, w, w.cash_customer, qty=5)  # 50 KWD
    col = s_service.create_collection(
        db,
        s_schemas.CollectionCreate(
            branch_id=w.branch.id,
            customer_id=w.cash_customer.id,
            collection_date=datetime.date.today(),
            total_amount=Decimal("50"),
            allocation_method=AllocationMethod.AUTO,
        ),
        company_id=w.company.id,
    )
    s_service.post_collection(db, col.id, company_id=w.company.id)
    db.refresh(inv)
    assert inv.status == InvoiceStatus.COLLECTED
    assert inv.amount_collected == Decimal("50.000")


def test_collection_manual_allocation(db_session, world):
    db = db_session
    w = world
    inv1 = _post_inv(db, w, w.cash_customer, qty=5)  # 50 KWD
    inv2 = _post_inv(db, w, w.cash_customer, qty=3)  # 30 KWD

    col = s_service.create_collection(
        db,
        s_schemas.CollectionCreate(
            branch_id=w.branch.id,
            customer_id=w.cash_customer.id,
            collection_date=datetime.date.today(),
            total_amount=Decimal("45"),
            allocation_method=AllocationMethod.MANUAL,
            lines=[
                s_schemas.CollectionLineCreate(invoice_id=inv1.id, amount_allocated=Decimal("30")),
                s_schemas.CollectionLineCreate(invoice_id=inv2.id, amount_allocated=Decimal("15")),
            ],
        ),
        company_id=w.company.id,
    )
    s_service.post_collection(db, col.id, company_id=w.company.id)
    db.refresh(inv1)
    db.refresh(inv2)
    assert inv1.amount_collected == Decimal("30.000")
    assert inv2.amount_collected == Decimal("15.000")


def test_collection_cancel_reverses_allocations(db_session, world):
    db = db_session
    w = world
    inv = _post_inv(db, w, w.cash_customer, qty=5)  # 50 KWD
    col = s_service.create_collection(
        db,
        s_schemas.CollectionCreate(
            branch_id=w.branch.id,
            customer_id=w.cash_customer.id,
            collection_date=datetime.date.today(),
            total_amount=Decimal("50"),
            allocation_method=AllocationMethod.AUTO,
        ),
        company_id=w.company.id,
    )
    s_service.post_collection(db, col.id, company_id=w.company.id)
    db.refresh(inv)
    assert inv.status == InvoiceStatus.COLLECTED

    s_service.cancel_collection(db, col.id, company_id=w.company.id)
    db.refresh(inv)
    assert inv.amount_collected == Decimal("0")
    assert inv.status == InvoiceStatus.POSTED


# ---------------------------------------------------------------------------
# Credit exposure
# ---------------------------------------------------------------------------


def test_credit_exposure_sums_open_invoices(db_session, world):
    db = db_session
    w = world
    inv1 = _create_inv(
        db, w.company.id, w.branch.id, w.credit_customer.id, w.price_list.id,
        [_line(w.product.id, w.warehouse.id, w.kg_unit.id, 2, "10.000")]  # 20 KWD
    )
    s_service.post_invoice(db, inv1.id, company_id=w.company.id)
    exposure = s_service._compute_credit_exposure(db, w.credit_customer.id)
    assert exposure == Decimal("20.000")

    # Partial collection of 5 KWD reduces exposure
    col = s_service.create_collection(
        db,
        s_schemas.CollectionCreate(
            branch_id=w.branch.id,
            customer_id=w.credit_customer.id,
            collection_date=datetime.date.today(),
            total_amount=Decimal("5"),
            allocation_method=AllocationMethod.AUTO,
        ),
        company_id=w.company.id,
    )
    s_service.post_collection(db, col.id, company_id=w.company.id)
    exposure2 = s_service._compute_credit_exposure(db, w.credit_customer.id)
    assert exposure2 == Decimal("15.000")


# ---------------------------------------------------------------------------
# Cross-company scoping
# ---------------------------------------------------------------------------


def test_invoice_not_found_across_companies(db_session, world):
    db = db_session
    w = world
    inv = _create_inv(
        db, w.company.id, w.branch.id, w.cash_customer.id, w.price_list.id,
        [_line(w.product.id, w.warehouse.id, w.kg_unit.id, 1, "10.000")]
    )
    other_co = _company(db, "OTHER")
    with pytest.raises(NotFoundError):
        s_service.get_invoice(db, inv.id, company_id=other_co.id)


def test_price_list_not_found_across_companies(db_session, world):
    db = db_session
    w = world
    other_co = _company(db, "OTHER2")
    with pytest.raises(NotFoundError):
        s_service.get_price_list(db, world.price_list.id, company_id=other_co.id)


# ---------------------------------------------------------------------------
# Misc: list functions
# ---------------------------------------------------------------------------


def test_list_invoices_filter_by_status(db_session, world):
    db = db_session
    w = world
    inv = _create_inv(
        db, w.company.id, w.branch.id, w.cash_customer.id, w.price_list.id,
        [_line(w.product.id, w.warehouse.id, w.kg_unit.id, 1, "10.000")]
    )
    drafts = s_service.list_invoices(db, w.company.id, status=InvoiceStatus.DRAFT)
    assert any(i.id == inv.id for i in drafts)
    posted = s_service.list_invoices(db, w.company.id, status=InvoiceStatus.POSTED)
    assert all(i.id != inv.id for i in posted)


def test_list_approval_requests_by_status(db_session, world):
    db = db_session
    w = world
    # Trigger a credit-limit approval
    inv = _create_inv(
        db, w.company.id, w.branch.id, w.credit_customer.id, w.price_list.id,
        [_line(w.product.id, w.warehouse.id, w.kg_unit.id, 20, "10.000")]
    )
    with pytest.raises(ApprovalRequired):
        s_service.post_invoice(db, inv.id, company_id=w.company.id, actor_id=w.actor.id)

    pending = s_service.list_approval_requests(
        db, w.company.id, status=ApprovalStatus.PENDING
    )
    assert len(pending) >= 1
    assert all(r.status == ApprovalStatus.PENDING for r in pending)
