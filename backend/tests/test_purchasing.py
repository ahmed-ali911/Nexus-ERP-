"""Purchasing module tests.

Covers: PO approve/cancel, GRN policy gating, posting (batch auto-create,
unit conversion, PO qty update), GRN cancel (approval + stock reversal),
supplier invoice (total, due-date, credit limit), purchase return (qty
guard, always-approval cycle, stock issued), supplier payment (FIFO, manual,
PAID transition, cancel reversal), backdated doc approval, maker-checker.

All tests run in a rolled-back transaction — nothing persists.
"""

import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.core.exceptions import ApprovalRequired, BusinessRuleViolation, NotFoundError
from app.modules.auth import schemas as auth_schemas
from app.modules.auth import service as auth_service
from app.modules.inventory import schemas as inv_schemas
from app.modules.inventory import service as inv_service
from app.modules.master_data import schemas as md_schemas
from app.modules.master_data import service as md_service
from app.modules.master_data.models import PaymentTerms, ProductType, SupplierType, UnitType
from app.modules.organization import schemas as org_schemas
from app.modules.organization import service as org_service
from app.modules.organization.models import BranchType, WarehouseType
from app.modules.purchasing import schemas as p_schemas
from app.modules.purchasing import service as p_service
from app.modules.purchasing.models import (
    BillStatus,
    GRNStatus,
    POStatus,
    PaymentAllocationMethod,
    PaymentStatus,
    PurchaseFlowPolicy,
    ReturnStatus,
)
from app.modules.shared.models import ApprovalStatus
from app.modules.shared import service as shared_service

# ---------------------------------------------------------------------------
# Low-level builders
# ---------------------------------------------------------------------------


def _company(db, code="PURCO"):
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


def _product(db, company_id, cat_id, base_unit_id, code="PROD", batch_tracked=False,
             purchase_unit_id=None):
    return md_service.create_product(
        db,
        md_schemas.ProductCreate(
            code=code,
            name_en=code,
            name_ar=code,
            category_id=cat_id,
            product_type=ProductType.RAW_MATERIAL,
            base_unit_id=base_unit_id,
            purchase_unit_id=purchase_unit_id,
            is_batch_tracked=batch_tracked,
        ),
        company_id=company_id,
    )


def _supplier(db, company_id, code="SUP", credit_limit=None, term_days=30):
    return md_service.create_supplier(
        db,
        md_schemas.SupplierCreate(
            code=code,
            name_en=code,
            name_ar=code,
            supplier_type=SupplierType.LOCAL,
            payment_terms=PaymentTerms.CREDIT,
            payment_term_days=term_days,
            credit_limit=credit_limit,
        ),
        company_id=company_id,
    )


def _user(db, company_id, username="actor1"):
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


def _conversion(db, company_id, from_id, to_id, factor, product_id=None):
    return md_service.create_conversion(
        db,
        md_schemas.UnitConversionCreate(
            from_unit_id=from_id,
            to_unit_id=to_id,
            factor=Decimal(str(factor)),
            product_id=product_id,
        ),
        company_id=company_id,
    )


def _settings(db, company_id, **kwargs):
    return p_service.update_settings(
        db,
        p_schemas.PurchaseSettingsUpdate(**kwargs),
        company_id=company_id,
    )


# ---------------------------------------------------------------------------
# Shared world fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def world(db_session):
    db = db_session
    co = _company(db)
    br = _branch(db, co.id)
    wh = _warehouse(db, br.id)

    gram = _unit(db, co.id, "G", UnitType.WEIGHT)
    kg = _unit(db, co.id, "KG", UnitType.WEIGHT)
    piece = _unit(db, co.id, "PC", UnitType.COUNT)

    _conversion(db, co.id, kg.id, gram.id, "1000")

    cat = _category(db, co.id)
    prod = _product(db, co.id, cat.id, gram.id, "RAWM")
    bp = _product(db, co.id, cat.id, gram.id, "BRAWM", batch_tracked=True)
    cnt_prod = _product(db, co.id, cat.id, piece.id, "CPROD")

    sup = _supplier(db, co.id)
    capped_sup = _supplier(
        db, co.id, "CAPSUP", credit_limit=Decimal("100"), term_days=15
    )

    actor = _user(db, co.id, "actor")
    approver = _user(db, co.id, "approver")

    return SimpleNamespace(
        company=co,
        branch=br,
        warehouse=wh,
        gram=gram,
        kg=kg,
        piece=piece,
        product=prod,
        batch_product=bp,
        cnt_product=cnt_prod,
        supplier=sup,
        capped_supplier=capped_sup,
        actor=actor,
        approver=approver,
    )


# ---------------------------------------------------------------------------
# Helper: build a posted GRN (direct receipt)
# ---------------------------------------------------------------------------


def _make_posted_grn(db, w, qty_g=5000, cost="0.005", product=None, batch_number=None):
    product = product or w.product
    grn = p_service.create_grn(
        db,
        p_schemas.GoodsReceiptCreate(
            branch_id=w.branch.id,
            supplier_id=w.supplier.id,
            receipt_date=datetime.date.today(),
            lines=[
                p_schemas.GRNLineCreate(
                    product_id=product.id,
                    warehouse_id=w.warehouse.id,
                    unit_id=w.gram.id,
                    quantity_received=Decimal(str(qty_g)),
                    unit_cost=Decimal(cost),
                    batch_number=batch_number,
                )
            ],
        ),
        company_id=w.company.id,
        actor_id=w.actor.id,
    )
    return p_service.post_grn(db, grn.id, w.company.id, w.actor.id)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def test_settings_default(world, db_session):
    db = db_session
    s = p_service.get_or_create_settings(db, world.company.id)
    assert s.purchase_flow_policy == PurchaseFlowPolicy.DIRECT_RECEIPT
    assert s.max_price_variance_pct == Decimal("0")


def test_settings_update(world, db_session):
    db = db_session
    s = _settings(db, world.company.id, max_price_variance_pct=Decimal("5.00"))
    assert s.max_price_variance_pct == Decimal("5.00")


# ---------------------------------------------------------------------------
# PurchaseOrder lifecycle
# ---------------------------------------------------------------------------


def test_po_create_and_approve(world, db_session):
    db = db_session
    po = p_service.create_po(
        db,
        p_schemas.PurchaseOrderCreate(
            branch_id=world.branch.id,
            supplier_id=world.supplier.id,
            po_date=datetime.date.today(),
            lines=[
                p_schemas.POLineCreate(
                    product_id=world.product.id,
                    unit_id=world.gram.id,
                    quantity_ordered=Decimal("10000"),
                    unit_cost=Decimal("0.005"),
                )
            ],
        ),
        company_id=world.company.id,
        actor_id=world.actor.id,
    )
    assert po.status == POStatus.DRAFT
    po = p_service.approve_po(db, po.id, world.company.id, world.approver.id)
    assert po.status == POStatus.APPROVED


def test_po_cancel_draft(world, db_session):
    db = db_session
    po = p_service.create_po(
        db,
        p_schemas.PurchaseOrderCreate(
            branch_id=world.branch.id,
            supplier_id=world.supplier.id,
            po_date=datetime.date.today(),
            lines=[
                p_schemas.POLineCreate(
                    product_id=world.product.id,
                    unit_id=world.gram.id,
                    quantity_ordered=Decimal("1000"),
                    unit_cost=Decimal("0.005"),
                )
            ],
        ),
        company_id=world.company.id,
    )
    po = p_service.cancel_po(db, po.id, world.company.id)
    assert po.status == POStatus.CANCELLED


def test_po_approve_nonexistent_raises(world, db_session):
    with pytest.raises(NotFoundError):
        p_service.approve_po(db_session, 999999, world.company.id)


# ---------------------------------------------------------------------------
# GRN — policy gating
# ---------------------------------------------------------------------------


def test_grn_direct_receipt_no_po_ok(world, db_session):
    db = db_session
    grn = p_service.create_grn(
        db,
        p_schemas.GoodsReceiptCreate(
            branch_id=world.branch.id,
            supplier_id=world.supplier.id,
            receipt_date=datetime.date.today(),
            lines=[
                p_schemas.GRNLineCreate(
                    product_id=world.product.id,
                    warehouse_id=world.warehouse.id,
                    unit_id=world.gram.id,
                    quantity_received=Decimal("1000"),
                    unit_cost=Decimal("0.005"),
                )
            ],
        ),
        company_id=world.company.id,
    )
    assert grn.status == GRNStatus.DRAFT


def test_grn_po_required_blocks_no_po(world, db_session):
    db = db_session
    _settings(db, world.company.id, purchase_flow_policy=PurchaseFlowPolicy.PO_REQUIRED)
    with pytest.raises(BusinessRuleViolation, match="requires an APPROVED PO"):
        p_service.create_grn(
            db,
            p_schemas.GoodsReceiptCreate(
                branch_id=world.branch.id,
                supplier_id=world.supplier.id,
                receipt_date=datetime.date.today(),
                lines=[
                    p_schemas.GRNLineCreate(
                        product_id=world.product.id,
                        warehouse_id=world.warehouse.id,
                        unit_id=world.gram.id,
                        quantity_received=Decimal("1000"),
                        unit_cost=Decimal("0.005"),
                    )
                ],
            ),
            company_id=world.company.id,
        )


def test_grn_po_required_accepts_approved_po(world, db_session):
    db = db_session
    _settings(db, world.company.id, purchase_flow_policy=PurchaseFlowPolicy.PO_REQUIRED)
    po = p_service.create_po(
        db,
        p_schemas.PurchaseOrderCreate(
            branch_id=world.branch.id,
            supplier_id=world.supplier.id,
            po_date=datetime.date.today(),
            lines=[
                p_schemas.POLineCreate(
                    product_id=world.product.id,
                    unit_id=world.gram.id,
                    quantity_ordered=Decimal("5000"),
                    unit_cost=Decimal("0.005"),
                )
            ],
        ),
        company_id=world.company.id,
    )
    po = p_service.approve_po(db, po.id, world.company.id)
    po_lines = p_service.get_po_detail(db, po.id, world.company.id)[1]
    grn = p_service.create_grn(
        db,
        p_schemas.GoodsReceiptCreate(
            branch_id=world.branch.id,
            supplier_id=world.supplier.id,
            purchase_order_id=po.id,
            receipt_date=datetime.date.today(),
            lines=[
                p_schemas.GRNLineCreate(
                    po_line_id=po_lines[0].id,
                    product_id=world.product.id,
                    warehouse_id=world.warehouse.id,
                    unit_id=world.gram.id,
                    quantity_received=Decimal("5000"),
                    unit_cost=Decimal("0.005"),
                )
            ],
        ),
        company_id=world.company.id,
    )
    assert grn.status == GRNStatus.DRAFT


# ---------------------------------------------------------------------------
# GRN — posting
# ---------------------------------------------------------------------------


def test_post_grn_creates_stock_movement(world, db_session):
    db = db_session
    grn = _make_posted_grn(db, world, qty_g=5000, cost="0.005")
    assert grn.status == GRNStatus.POSTED

    _, lines = p_service.get_grn_detail(db, grn.id, world.company.id)
    assert lines[0].stock_movement_id is not None

    balances = inv_service.list_balances(
        db, world.company.id, warehouse_id=world.warehouse.id, product_id=world.product.id
    )
    assert sum(b.quantity_on_hand for b in balances) == Decimal("5000")


def test_post_grn_updates_po_qty(world, db_session):
    db = db_session
    po = p_service.create_po(
        db,
        p_schemas.PurchaseOrderCreate(
            branch_id=world.branch.id,
            supplier_id=world.supplier.id,
            po_date=datetime.date.today(),
            lines=[
                p_schemas.POLineCreate(
                    product_id=world.product.id,
                    unit_id=world.gram.id,
                    quantity_ordered=Decimal("10000"),
                    unit_cost=Decimal("0.005"),
                )
            ],
        ),
        company_id=world.company.id,
    )
    po = p_service.approve_po(db, po.id, world.company.id)
    po_lines = p_service.get_po_detail(db, po.id, world.company.id)[1]

    grn = p_service.create_grn(
        db,
        p_schemas.GoodsReceiptCreate(
            branch_id=world.branch.id,
            supplier_id=world.supplier.id,
            purchase_order_id=po.id,
            receipt_date=datetime.date.today(),
            lines=[
                p_schemas.GRNLineCreate(
                    po_line_id=po_lines[0].id,
                    product_id=world.product.id,
                    warehouse_id=world.warehouse.id,
                    unit_id=world.gram.id,
                    quantity_received=Decimal("5000"),
                    unit_cost=Decimal("0.005"),
                )
            ],
        ),
        company_id=world.company.id,
    )
    p_service.post_grn(db, grn.id, world.company.id)
    db.refresh(po_lines[0])
    assert po_lines[0].quantity_received == Decimal("5000")


def test_post_grn_auto_creates_batch(world, db_session):
    db = db_session
    grn = p_service.create_grn(
        db,
        p_schemas.GoodsReceiptCreate(
            branch_id=world.branch.id,
            supplier_id=world.supplier.id,
            receipt_date=datetime.date.today(),
            lines=[
                p_schemas.GRNLineCreate(
                    product_id=world.batch_product.id,
                    warehouse_id=world.warehouse.id,
                    unit_id=world.gram.id,
                    quantity_received=Decimal("3000"),
                    unit_cost=Decimal("0.010"),
                    batch_number="B-AUTO-001",
                    expiry_date=datetime.date.today() + datetime.timedelta(days=180),
                )
            ],
        ),
        company_id=world.company.id,
    )
    p_service.post_grn(db, grn.id, world.company.id)
    _, lines = p_service.get_grn_detail(db, grn.id, world.company.id)
    assert lines[0].batch_id is not None


def test_post_grn_batch_required_raises(world, db_session):
    db = db_session
    grn = p_service.create_grn(
        db,
        p_schemas.GoodsReceiptCreate(
            branch_id=world.branch.id,
            supplier_id=world.supplier.id,
            receipt_date=datetime.date.today(),
            lines=[
                p_schemas.GRNLineCreate(
                    product_id=world.batch_product.id,
                    warehouse_id=world.warehouse.id,
                    unit_id=world.gram.id,
                    quantity_received=Decimal("3000"),
                    unit_cost=Decimal("0.010"),
                )
            ],
        ),
        company_id=world.company.id,
    )
    with pytest.raises(BusinessRuleViolation, match="batch-tracked"):
        p_service.post_grn(db, grn.id, world.company.id)


def test_post_grn_unit_conversion(world, db_session):
    """Receive 5 KG — stock ledger must show 5000 grams."""
    db = db_session
    grn = p_service.create_grn(
        db,
        p_schemas.GoodsReceiptCreate(
            branch_id=world.branch.id,
            supplier_id=world.supplier.id,
            receipt_date=datetime.date.today(),
            lines=[
                p_schemas.GRNLineCreate(
                    product_id=world.product.id,
                    warehouse_id=world.warehouse.id,
                    unit_id=world.kg.id,
                    quantity_received=Decimal("5"),
                    unit_cost=Decimal("5.000"),
                )
            ],
        ),
        company_id=world.company.id,
    )
    p_service.post_grn(db, grn.id, world.company.id)
    balances = inv_service.list_balances(
        db, world.company.id, warehouse_id=world.warehouse.id, product_id=world.product.id
    )
    assert sum(b.quantity_on_hand for b in balances) == Decimal("5000")


def test_post_grn_price_variance_triggers_approval(world, db_session):
    """max_price_variance_pct = 0 → any deviation raises ApprovalRequired."""
    db = db_session
    po = p_service.create_po(
        db,
        p_schemas.PurchaseOrderCreate(
            branch_id=world.branch.id,
            supplier_id=world.supplier.id,
            po_date=datetime.date.today(),
            lines=[
                p_schemas.POLineCreate(
                    product_id=world.product.id,
                    unit_id=world.gram.id,
                    quantity_ordered=Decimal("10000"),
                    unit_cost=Decimal("0.005"),
                )
            ],
        ),
        company_id=world.company.id,
    )
    po = p_service.approve_po(db, po.id, world.company.id)
    po_lines = p_service.get_po_detail(db, po.id, world.company.id)[1]

    grn = p_service.create_grn(
        db,
        p_schemas.GoodsReceiptCreate(
            branch_id=world.branch.id,
            supplier_id=world.supplier.id,
            purchase_order_id=po.id,
            receipt_date=datetime.date.today(),
            lines=[
                p_schemas.GRNLineCreate(
                    po_line_id=po_lines[0].id,
                    product_id=world.product.id,
                    warehouse_id=world.warehouse.id,
                    unit_id=world.gram.id,
                    quantity_received=Decimal("5000"),
                    unit_cost=Decimal("0.006"),  # higher than PO cost → variance
                )
            ],
        ),
        company_id=world.company.id,
    )
    with pytest.raises(ApprovalRequired):
        p_service.post_grn(db, grn.id, world.company.id, actor_id=world.actor.id)


def test_post_grn_price_variance_proceeds_after_approval(world, db_session):
    """After PURCHASE_PRICE_OVERRIDE approved, post_grn proceeds."""
    db = db_session
    po = p_service.create_po(
        db,
        p_schemas.PurchaseOrderCreate(
            branch_id=world.branch.id,
            supplier_id=world.supplier.id,
            po_date=datetime.date.today(),
            lines=[
                p_schemas.POLineCreate(
                    product_id=world.product.id,
                    unit_id=world.gram.id,
                    quantity_ordered=Decimal("10000"),
                    unit_cost=Decimal("0.005"),
                )
            ],
        ),
        company_id=world.company.id,
    )
    po = p_service.approve_po(db, po.id, world.company.id)
    po_lines = p_service.get_po_detail(db, po.id, world.company.id)[1]

    grn = p_service.create_grn(
        db,
        p_schemas.GoodsReceiptCreate(
            branch_id=world.branch.id,
            supplier_id=world.supplier.id,
            purchase_order_id=po.id,
            receipt_date=datetime.date.today(),
            lines=[
                p_schemas.GRNLineCreate(
                    po_line_id=po_lines[0].id,
                    product_id=world.product.id,
                    warehouse_id=world.warehouse.id,
                    unit_id=world.gram.id,
                    quantity_received=Decimal("5000"),
                    unit_cost=Decimal("0.006"),
                )
            ],
        ),
        company_id=world.company.id,
    )
    # First call raises and creates approval request
    with pytest.raises(ApprovalRequired) as exc_info:
        p_service.post_grn(db, grn.id, world.company.id, actor_id=world.actor.id)

    approval_id = exc_info.value.approval_request_id
    # Approver approves (different user → maker-checker ok)
    shared_service.approve_request(db, approval_id, world.company.id, world.approver.id)

    # Second call should succeed now
    grn = p_service.post_grn(db, grn.id, world.company.id, actor_id=world.actor.id)
    assert grn.status == GRNStatus.POSTED


# ---------------------------------------------------------------------------
# GRN — cancel
# ---------------------------------------------------------------------------


def test_cancel_grn_draft_no_approval(world, db_session):
    db = db_session
    grn = p_service.create_grn(
        db,
        p_schemas.GoodsReceiptCreate(
            branch_id=world.branch.id,
            supplier_id=world.supplier.id,
            receipt_date=datetime.date.today(),
            lines=[
                p_schemas.GRNLineCreate(
                    product_id=world.product.id,
                    warehouse_id=world.warehouse.id,
                    unit_id=world.gram.id,
                    quantity_received=Decimal("1000"),
                    unit_cost=Decimal("0.005"),
                )
            ],
        ),
        company_id=world.company.id,
    )
    grn = p_service.cancel_grn(db, grn.id, world.company.id)
    assert grn.status == GRNStatus.CANCELLED


def test_cancel_grn_posted_requires_approval(world, db_session):
    db = db_session
    grn = _make_posted_grn(db, world, qty_g=2000)
    with pytest.raises(ApprovalRequired):
        p_service.cancel_grn(db, grn.id, world.company.id, actor_id=world.actor.id)


def test_cancel_grn_posted_reverses_stock(world, db_session):
    db = db_session
    grn = _make_posted_grn(db, world, qty_g=2000)

    balances_before = inv_service.list_balances(
        db, world.company.id, warehouse_id=world.warehouse.id, product_id=world.product.id
    )
    assert sum(b.quantity_on_hand for b in balances_before) == Decimal("2000")

    with pytest.raises(ApprovalRequired) as exc_info:
        p_service.cancel_grn(db, grn.id, world.company.id, actor_id=world.actor.id)

    shared_service.approve_request(
        db, exc_info.value.approval_request_id, world.company.id, world.approver.id
    )

    grn = p_service.cancel_grn(db, grn.id, world.company.id, actor_id=world.actor.id)
    assert grn.status == GRNStatus.CANCELLED

    balances_after = inv_service.list_balances(
        db, world.company.id, warehouse_id=world.warehouse.id, product_id=world.product.id
    )
    assert sum(b.quantity_on_hand for b in balances_after) == Decimal("0")


# ---------------------------------------------------------------------------
# SupplierInvoice
# ---------------------------------------------------------------------------


def test_create_and_post_bill(world, db_session):
    db = db_session
    grn = _make_posted_grn(db, world, qty_g=5000, cost="0.005")
    _, grn_lines = p_service.get_grn_detail(db, grn.id, world.company.id)

    bill = p_service.create_supplier_invoice(
        db,
        p_schemas.SupplierInvoiceCreate(
            branch_id=world.branch.id,
            supplier_id=world.supplier.id,
            goods_receipt_id=grn.id,
            bill_date=datetime.date.today(),
            lines=[
                p_schemas.BillLineCreate(
                    grn_line_id=grn_lines[0].id,
                    product_id=world.product.id,
                    unit_id=world.gram.id,
                    quantity=Decimal("5000"),
                    unit_cost=Decimal("0.005"),
                )
            ],
        ),
        company_id=world.company.id,
    )
    assert bill.grand_total == Decimal("25.000")  # 5000 * 0.005

    bill = p_service.post_supplier_invoice(db, bill.id, world.company.id)
    assert bill.status == BillStatus.POSTED
    assert bill.due_date is not None


def test_bill_due_date_uses_supplier_payment_terms(world, db_session):
    db = db_session
    grn = _make_posted_grn(db, world, qty_g=1000, cost="0.005")
    _, grn_lines = p_service.get_grn_detail(db, grn.id, world.company.id)

    bill = p_service.create_supplier_invoice(
        db,
        p_schemas.SupplierInvoiceCreate(
            branch_id=world.branch.id,
            supplier_id=world.supplier.id,
            goods_receipt_id=grn.id,
            bill_date=datetime.date.today(),
            lines=[
                p_schemas.BillLineCreate(
                    product_id=world.product.id,
                    unit_id=world.gram.id,
                    quantity=Decimal("1000"),
                    unit_cost=Decimal("0.005"),
                )
            ],
        ),
        company_id=world.company.id,
    )
    bill = p_service.post_supplier_invoice(db, bill.id, world.company.id)
    # supplier default is 30 days
    expected_due = datetime.date.today() + datetime.timedelta(days=30)
    assert bill.due_date == expected_due


def test_bill_credit_limit_triggers_approval(world, db_session):
    """Supplier credit limit 100 KWD; bill for 150 → approval required."""
    db = db_session
    # disable the 'allow_supplier_over_credit_limit' flag (default = True in model)
    _settings(db, world.company.id, allow_supplier_over_credit_limit=False)

    grn = p_service.create_grn(
        db,
        p_schemas.GoodsReceiptCreate(
            branch_id=world.branch.id,
            supplier_id=world.capped_supplier.id,
            receipt_date=datetime.date.today(),
            lines=[
                p_schemas.GRNLineCreate(
                    product_id=world.product.id,
                    warehouse_id=world.warehouse.id,
                    unit_id=world.gram.id,
                    quantity_received=Decimal("1000"),
                    unit_cost=Decimal("0.005"),
                )
            ],
        ),
        company_id=world.company.id,
    )
    p_service.post_grn(db, grn.id, world.company.id)

    bill = p_service.create_supplier_invoice(
        db,
        p_schemas.SupplierInvoiceCreate(
            branch_id=world.branch.id,
            supplier_id=world.capped_supplier.id,
            goods_receipt_id=grn.id,
            bill_date=datetime.date.today(),
            lines=[
                p_schemas.BillLineCreate(
                    product_id=world.product.id,
                    unit_id=world.gram.id,
                    quantity=Decimal("1000"),
                    unit_cost=Decimal("0.150"),  # 150 KWD > 100 limit
                )
            ],
        ),
        company_id=world.company.id,
    )
    with pytest.raises(ApprovalRequired):
        p_service.post_supplier_invoice(
            db, bill.id, world.company.id, actor_id=world.actor.id
        )


def test_cancel_posted_bill_requires_approval(world, db_session):
    db = db_session
    grn = _make_posted_grn(db, world)
    _, gl = p_service.get_grn_detail(db, grn.id, world.company.id)
    bill = p_service.create_supplier_invoice(
        db,
        p_schemas.SupplierInvoiceCreate(
            branch_id=world.branch.id,
            supplier_id=world.supplier.id,
            bill_date=datetime.date.today(),
            lines=[
                p_schemas.BillLineCreate(
                    product_id=world.product.id,
                    unit_id=world.gram.id,
                    quantity=Decimal("5000"),
                    unit_cost=Decimal("0.005"),
                )
            ],
        ),
        company_id=world.company.id,
    )
    p_service.post_supplier_invoice(db, bill.id, world.company.id)
    with pytest.raises(ApprovalRequired):
        p_service.cancel_supplier_invoice(
            db, bill.id, world.company.id, actor_id=world.actor.id
        )


# ---------------------------------------------------------------------------
# PurchaseReturn
# ---------------------------------------------------------------------------


def test_return_qty_guard(world, db_session):
    """Cannot return more than received."""
    db = db_session
    grn = _make_posted_grn(db, world, qty_g=1000)
    _, grn_lines = p_service.get_grn_detail(db, grn.id, world.company.id)

    with pytest.raises(BusinessRuleViolation, match="returnable"):
        p_service.create_purchase_return(
            db,
            p_schemas.PurchaseReturnCreate(
                branch_id=world.branch.id,
                supplier_id=world.supplier.id,
                original_grn_id=grn.id,
                return_date=datetime.date.today(),
                lines=[
                    p_schemas.ReturnLineCreate(
                        original_grn_line_id=grn_lines[0].id,
                        quantity_returned=Decimal("9999"),
                    )
                ],
            ),
            company_id=world.company.id,
        )


def test_return_always_requires_approval(world, db_session):
    db = db_session
    grn = _make_posted_grn(db, world, qty_g=5000)
    _, grn_lines = p_service.get_grn_detail(db, grn.id, world.company.id)

    ret = p_service.create_purchase_return(
        db,
        p_schemas.PurchaseReturnCreate(
            branch_id=world.branch.id,
            supplier_id=world.supplier.id,
            original_grn_id=grn.id,
            return_date=datetime.date.today(),
            lines=[
                p_schemas.ReturnLineCreate(
                    original_grn_line_id=grn_lines[0].id,
                    quantity_returned=Decimal("1000"),
                )
            ],
        ),
        company_id=world.company.id,
    )
    with pytest.raises(ApprovalRequired):
        p_service.post_purchase_return(
            db, ret.id, world.company.id, actor_id=world.actor.id
        )


def test_return_posts_after_approval_and_issues_stock(world, db_session):
    db = db_session
    grn = _make_posted_grn(db, world, qty_g=5000)
    _, grn_lines = p_service.get_grn_detail(db, grn.id, world.company.id)

    ret = p_service.create_purchase_return(
        db,
        p_schemas.PurchaseReturnCreate(
            branch_id=world.branch.id,
            supplier_id=world.supplier.id,
            original_grn_id=grn.id,
            return_date=datetime.date.today(),
            lines=[
                p_schemas.ReturnLineCreate(
                    original_grn_line_id=grn_lines[0].id,
                    quantity_returned=Decimal("2000"),
                )
            ],
        ),
        company_id=world.company.id,
    )

    with pytest.raises(ApprovalRequired) as exc_info:
        p_service.post_purchase_return(
            db, ret.id, world.company.id, actor_id=world.actor.id
        )

    shared_service.approve_request(
        db, exc_info.value.approval_request_id, world.company.id, world.approver.id
    )

    ret = p_service.post_purchase_return(
        db, ret.id, world.company.id, actor_id=world.actor.id
    )
    assert ret.status == ReturnStatus.POSTED

    balances = inv_service.list_balances(
        db, world.company.id, warehouse_id=world.warehouse.id, product_id=world.product.id
    )
    # 5000 received - 2000 returned
    assert sum(b.quantity_on_hand for b in balances) == Decimal("3000")


def test_return_double_return_blocked(world, db_session):
    """Two returns that together exceed received qty are blocked on the second."""
    db = db_session
    grn = _make_posted_grn(db, world, qty_g=5000)
    _, grn_lines = p_service.get_grn_detail(db, grn.id, world.company.id)

    ret1 = p_service.create_purchase_return(
        db,
        p_schemas.PurchaseReturnCreate(
            branch_id=world.branch.id,
            supplier_id=world.supplier.id,
            original_grn_id=grn.id,
            return_date=datetime.date.today(),
            lines=[
                p_schemas.ReturnLineCreate(
                    original_grn_line_id=grn_lines[0].id,
                    quantity_returned=Decimal("3000"),
                )
            ],
        ),
        company_id=world.company.id,
    )
    with pytest.raises(ApprovalRequired) as exc_info:
        p_service.post_purchase_return(
            db, ret1.id, world.company.id, actor_id=world.actor.id
        )
    shared_service.approve_request(
        db, exc_info.value.approval_request_id, world.company.id, world.approver.id
    )
    p_service.post_purchase_return(db, ret1.id, world.company.id, actor_id=world.actor.id)

    # Now try to return 3000 more when only 2000 remain
    with pytest.raises(BusinessRuleViolation, match="returnable"):
        p_service.create_purchase_return(
            db,
            p_schemas.PurchaseReturnCreate(
                branch_id=world.branch.id,
                supplier_id=world.supplier.id,
                original_grn_id=grn.id,
                return_date=datetime.date.today(),
                lines=[
                    p_schemas.ReturnLineCreate(
                        original_grn_line_id=grn_lines[0].id,
                        quantity_returned=Decimal("3000"),
                    )
                ],
            ),
            company_id=world.company.id,
        )


def test_return_to_batch_product(world, db_session):
    """Return a batch-tracked product: stock must drop, approval required."""
    db = db_session
    grn = p_service.create_grn(
        db,
        p_schemas.GoodsReceiptCreate(
            branch_id=world.branch.id,
            supplier_id=world.supplier.id,
            receipt_date=datetime.date.today(),
            lines=[
                p_schemas.GRNLineCreate(
                    product_id=world.batch_product.id,
                    warehouse_id=world.warehouse.id,
                    unit_id=world.gram.id,
                    quantity_received=Decimal("4000"),
                    unit_cost=Decimal("0.010"),
                    batch_number="BATCH-RET-001",
                    expiry_date=datetime.date.today() + datetime.timedelta(days=120),
                )
            ],
        ),
        company_id=world.company.id,
    )
    p_service.post_grn(db, grn.id, world.company.id)
    _, grn_lines = p_service.get_grn_detail(db, grn.id, world.company.id)

    ret = p_service.create_purchase_return(
        db,
        p_schemas.PurchaseReturnCreate(
            branch_id=world.branch.id,
            supplier_id=world.supplier.id,
            original_grn_id=grn.id,
            return_date=datetime.date.today(),
            lines=[
                p_schemas.ReturnLineCreate(
                    original_grn_line_id=grn_lines[0].id,
                    quantity_returned=Decimal("2000"),
                )
            ],
        ),
        company_id=world.company.id,
    )

    with pytest.raises(ApprovalRequired) as exc_info:
        p_service.post_purchase_return(
            db, ret.id, world.company.id, actor_id=world.actor.id
        )
    shared_service.approve_request(
        db, exc_info.value.approval_request_id, world.company.id, world.approver.id
    )
    p_service.post_purchase_return(db, ret.id, world.company.id, actor_id=world.actor.id)

    balances = inv_service.list_balances(
        db, world.company.id, warehouse_id=world.warehouse.id, product_id=world.batch_product.id
    )
    assert sum(b.quantity_on_hand for b in balances) == Decimal("2000")


# ---------------------------------------------------------------------------
# SupplierPayment — FIFO auto-allocation
# ---------------------------------------------------------------------------


def _post_bill(db, world, amount):
    """Helper: create a GRN + bill for `amount` KWD (posting unit_cost in grams)."""
    grn = p_service.create_grn(
        db,
        p_schemas.GoodsReceiptCreate(
            branch_id=world.branch.id,
            supplier_id=world.supplier.id,
            receipt_date=datetime.date.today(),
            lines=[
                p_schemas.GRNLineCreate(
                    product_id=world.product.id,
                    warehouse_id=world.warehouse.id,
                    unit_id=world.gram.id,
                    quantity_received=Decimal("1000"),
                    unit_cost=Decimal(str(amount)) / 1000,
                )
            ],
        ),
        company_id=world.company.id,
    )
    p_service.post_grn(db, grn.id, world.company.id)
    bill = p_service.create_supplier_invoice(
        db,
        p_schemas.SupplierInvoiceCreate(
            branch_id=world.branch.id,
            supplier_id=world.supplier.id,
            goods_receipt_id=grn.id,
            bill_date=datetime.date.today(),
            lines=[
                p_schemas.BillLineCreate(
                    product_id=world.product.id,
                    unit_id=world.gram.id,
                    quantity=Decimal("1000"),
                    unit_cost=Decimal(str(amount)) / 1000,
                )
            ],
        ),
        company_id=world.company.id,
    )
    p_service.post_supplier_invoice(db, bill.id, world.company.id)
    return bill


def test_payment_fifo_auto_allocation(world, db_session):
    db = db_session
    bill1 = _post_bill(db, world, "30")  # 30 KWD
    bill2 = _post_bill(db, world, "50")  # 50 KWD

    payment = p_service.create_supplier_payment(
        db,
        p_schemas.SupplierPaymentCreate(
            branch_id=world.branch.id,
            supplier_id=world.supplier.id,
            payment_date=datetime.date.today(),
            total_amount=Decimal("40"),
            allocation_method=PaymentAllocationMethod.AUTO,
        ),
        company_id=world.company.id,
    )
    p_service.post_supplier_payment(db, payment.id, world.company.id)

    db.refresh(bill1)
    db.refresh(bill2)
    # FIFO: bill1 fully paid (30), remaining 10 applied to bill2
    assert bill1.status == BillStatus.PAID
    assert bill1.amount_paid == Decimal("30")
    assert bill2.amount_paid == Decimal("10")
    assert bill2.status == BillStatus.POSTED  # not fully paid


def test_payment_auto_marks_bill_paid(world, db_session):
    db = db_session
    bill = _post_bill(db, world, "25")

    payment = p_service.create_supplier_payment(
        db,
        p_schemas.SupplierPaymentCreate(
            branch_id=world.branch.id,
            supplier_id=world.supplier.id,
            payment_date=datetime.date.today(),
            total_amount=Decimal("25"),
        ),
        company_id=world.company.id,
    )
    p_service.post_supplier_payment(db, payment.id, world.company.id)

    db.refresh(bill)
    assert bill.status == BillStatus.PAID


def test_payment_manual_allocation(world, db_session):
    db = db_session
    bill = _post_bill(db, world, "60")

    payment = p_service.create_supplier_payment(
        db,
        p_schemas.SupplierPaymentCreate(
            branch_id=world.branch.id,
            supplier_id=world.supplier.id,
            payment_date=datetime.date.today(),
            total_amount=Decimal("60"),
            allocation_method=PaymentAllocationMethod.MANUAL,
            lines=[
                p_schemas.PaymentLineCreate(
                    bill_id=bill.id, amount_applied=Decimal("60")
                )
            ],
        ),
        company_id=world.company.id,
    )
    p_service.post_supplier_payment(db, payment.id, world.company.id)
    db.refresh(bill)
    assert bill.status == BillStatus.PAID


def test_cancel_payment_reverses_allocation(world, db_session):
    db = db_session
    bill = _post_bill(db, world, "30")

    payment = p_service.create_supplier_payment(
        db,
        p_schemas.SupplierPaymentCreate(
            branch_id=world.branch.id,
            supplier_id=world.supplier.id,
            payment_date=datetime.date.today(),
            total_amount=Decimal("30"),
        ),
        company_id=world.company.id,
    )
    p_service.post_supplier_payment(db, payment.id, world.company.id)
    db.refresh(bill)
    assert bill.status == BillStatus.PAID

    p_service.cancel_supplier_payment(db, payment.id, world.company.id)
    db.refresh(bill)
    assert bill.status == BillStatus.POSTED
    assert bill.amount_paid == Decimal("0")


# ---------------------------------------------------------------------------
# Backdated document
# ---------------------------------------------------------------------------


def test_backdated_grn_requires_approval(world, db_session):
    db = db_session
    _settings(db, world.company.id, allow_backdated_purchase_docs=False)

    grn = p_service.create_grn(
        db,
        p_schemas.GoodsReceiptCreate(
            branch_id=world.branch.id,
            supplier_id=world.supplier.id,
            receipt_date=datetime.date.today() - datetime.timedelta(days=3),
            lines=[
                p_schemas.GRNLineCreate(
                    product_id=world.product.id,
                    warehouse_id=world.warehouse.id,
                    unit_id=world.gram.id,
                    quantity_received=Decimal("1000"),
                    unit_cost=Decimal("0.005"),
                )
            ],
        ),
        company_id=world.company.id,
    )
    with pytest.raises(ApprovalRequired):
        p_service.post_grn(db, grn.id, world.company.id, actor_id=world.actor.id)


# ---------------------------------------------------------------------------
# Maker-checker
# ---------------------------------------------------------------------------


def test_maker_checker_grn_cancel(world, db_session):
    """Actor who requested cancel cannot approve their own cancel request."""
    db = db_session
    grn = _make_posted_grn(db, world, qty_g=1000)

    with pytest.raises(ApprovalRequired) as exc_info:
        p_service.cancel_grn(db, grn.id, world.company.id, actor_id=world.actor.id)

    approval_id = exc_info.value.approval_request_id
    with pytest.raises(BusinessRuleViolation, match="maker-checker"):
        shared_service.approve_request(
            db, approval_id, world.company.id, world.actor.id  # same user!
        )


# ---------------------------------------------------------------------------
# Sequence numbers
# ---------------------------------------------------------------------------


def test_sequence_numbers_increment(world, db_session):
    db = db_session
    po1 = p_service.create_po(
        db,
        p_schemas.PurchaseOrderCreate(
            branch_id=world.branch.id,
            supplier_id=world.supplier.id,
            po_date=datetime.date.today(),
            lines=[
                p_schemas.POLineCreate(
                    product_id=world.product.id,
                    unit_id=world.gram.id,
                    quantity_ordered=Decimal("100"),
                    unit_cost=Decimal("0.005"),
                )
            ],
        ),
        company_id=world.company.id,
    )
    po2 = p_service.create_po(
        db,
        p_schemas.PurchaseOrderCreate(
            branch_id=world.branch.id,
            supplier_id=world.supplier.id,
            po_date=datetime.date.today(),
            lines=[
                p_schemas.POLineCreate(
                    product_id=world.product.id,
                    unit_id=world.gram.id,
                    quantity_ordered=Decimal("100"),
                    unit_cost=Decimal("0.005"),
                )
            ],
        ),
        company_id=world.company.id,
    )
    assert po1.po_number != po2.po_number
    # Both should follow the PO-YEAR-NNNNN pattern
    assert po1.po_number.startswith("PO-")
    assert po2.po_number.startswith("PO-")
