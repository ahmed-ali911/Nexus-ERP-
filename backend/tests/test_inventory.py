"""Inventory module tests.

Covers: settings, batch CRUD, receive/issue/transfer/adjust, reversal,
negative-stock guard, weighted-average costing, FEFO suggestion,
expiry filtering, batch-tracking validation.
"""

import datetime
from decimal import Decimal

import pytest

from app.core.exceptions import BusinessRuleViolation, NotFoundError
from app.modules.inventory import schemas, service
from app.modules.inventory.models import CostingMethod, MovementType
from app.modules.master_data import schemas as md_schemas
from app.modules.master_data import service as md_service
from app.modules.master_data.models import ProductType, UnitType
from app.modules.organization import schemas as org_schemas
from app.modules.organization import service as org_service
from app.modules.organization.models import BranchType, WarehouseType

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_company(db, code="INVCO"):
    return org_service.create_company(
        db,
        org_schemas.CompanyCreate(
            code=code,
            name_en=f"{code} Co",
            name_ar=f"شركة {code}",
            commercial_registration_no=f"CR-{code}",
        ),
    )


def _make_branch(db, company_id, code="BR1"):
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


def _make_warehouse(db, branch_id, code="WH1", wh_type=WarehouseType.FINISHED_GOODS):
    return org_service.create_warehouse(
        db,
        org_schemas.WarehouseCreate(
            branch_id=branch_id,
            code=code,
            name_en=code,
            name_ar=code,
            warehouse_type=wh_type,
        ),
    )


def _make_unit(db, company_id, code, unit_type=UnitType.WEIGHT):
    return md_service.create_unit(
        db,
        md_schemas.UnitOfMeasureCreate(
            code=code,
            name_en=code,
            name_ar=code,
            symbol=code[:3],
            unit_type=unit_type,
        ),
        company_id=company_id,
    )


def _make_category(db, company_id, code="CAT"):
    return md_service.create_category(
        db,
        md_schemas.CategoryCreate(code=code, name_en=code, name_ar=code),
        company_id=company_id,
    )


def _make_product(
    db,
    company_id,
    category_id,
    base_unit_id,
    code="PROD",
    is_batch_tracked=False,
):
    return md_service.create_product(
        db,
        md_schemas.ProductCreate(
            code=code,
            name_en=code,
            name_ar=code,
            category_id=category_id,
            product_type=ProductType.FINISHED_GOOD,
            base_unit_id=base_unit_id,
            is_batch_tracked=is_batch_tracked,
        ),
        company_id=company_id,
    )


def _make_batch(db, company_id, product_id, number="B001", days_to_expiry=90):
    return service.create_batch(
        db,
        schemas.BatchCreate(
            product_id=product_id,
            batch_number=number,
            expiry_date=datetime.date.today() + datetime.timedelta(days=days_to_expiry),
        ),
        company_id=company_id,
    )


def _recv(db, company_id, warehouse_id, product_id, qty, cost, batch_id=None, notes=None):
    """Brevity wrapper for receive_stock in tests."""
    return service.receive_stock(
        db,
        schemas.ReceiveStockRequest(
            warehouse_id=warehouse_id,
            product_id=product_id,
            batch_id=batch_id,
            quantity=Decimal(str(qty)),
            unit_cost=Decimal(str(cost)),
            notes=notes,
        ),
        company_id=company_id,
    )


def _issue(db, company_id, warehouse_id, product_id, qty, batch_id=None, approved=False):
    """Brevity wrapper for issue_stock in tests."""
    return service.issue_stock(
        db,
        schemas.IssueStockRequest(
            warehouse_id=warehouse_id,
            product_id=product_id,
            batch_id=batch_id,
            quantity=Decimal(str(qty)),
            approved_negative=approved,
        ),
        company_id=company_id,
    )


def _bal(db, company_id, warehouse_id, product_id, batch_id=None):
    """Brevity wrapper for _get_balance in tests."""
    return service._get_balance(db, company_id, warehouse_id, product_id, batch_id)


@pytest.fixture()
def world(db_session):
    """Returns a dict with company, branch, two warehouses, units, and products."""
    db = db_session
    company = _make_company(db)
    branch = _make_branch(db, company.id)
    wh1 = _make_warehouse(db, branch.id, "WH1")
    wh2 = _make_warehouse(db, branch.id, "WH2")
    gram = _make_unit(db, company.id, "G", UnitType.WEIGHT)
    piece = _make_unit(db, company.id, "PC", UnitType.COUNT)
    cat = _make_category(db, company.id)
    batch_prod = _make_product(db, company.id, cat.id, gram.id, "BPROD", is_batch_tracked=True)
    plain_prod = _make_product(db, company.id, cat.id, piece.id, "PPROD", is_batch_tracked=False)
    return {
        "db": db,
        "company": company,
        "branch": branch,
        "wh1": wh1,
        "wh2": wh2,
        "gram": gram,
        "piece": piece,
        "cat": cat,
        "batch_prod": batch_prod,
        "plain_prod": plain_prod,
    }


# ---------------------------------------------------------------------------
# InventorySettings
# ---------------------------------------------------------------------------


def test_settings_created_on_first_access(world):
    db, company = world["db"], world["company"]
    settings = service.get_or_create_settings(db, company.id)
    assert settings.company_id == company.id
    assert settings.costing_method == CostingMethod.WEIGHTED_AVERAGE
    assert settings.allow_negative_stock is False


def test_settings_idempotent(world):
    db, company = world["db"], world["company"]
    s1 = service.get_or_create_settings(db, company.id)
    s2 = service.get_or_create_settings(db, company.id)
    assert s1.id == s2.id


# ---------------------------------------------------------------------------
# Batch CRUD
# ---------------------------------------------------------------------------


def test_create_batch_for_batch_tracked_product(world):
    db, company, batch_prod = world["db"], world["company"], world["batch_prod"]
    batch = _make_batch(db, company.id, batch_prod.id, "B001")
    assert batch.id is not None
    assert batch.batch_number == "B001"
    assert batch.company_id == company.id


def test_create_batch_rejected_for_non_batch_tracked(world):
    db, company, plain_prod = world["db"], world["company"], world["plain_prod"]
    with pytest.raises(BusinessRuleViolation, match="not batch-tracked"):
        service.create_batch(
            db,
            schemas.BatchCreate(product_id=plain_prod.id, batch_number="X"),
            company_id=company.id,
        )


def test_list_batches_by_product(world):
    db, company, batch_prod = world["db"], world["company"], world["batch_prod"]
    _make_batch(db, company.id, batch_prod.id, "B001")
    _make_batch(db, company.id, batch_prod.id, "B002", days_to_expiry=10)
    batches = service.list_batches(db, company_id=company.id, product_id=batch_prod.id)
    assert len(batches) == 2


def test_get_batch_not_found(world):
    db = world["db"]
    with pytest.raises(NotFoundError):
        service.get_batch(db, 9999999)


# ---------------------------------------------------------------------------
# receive_stock
# ---------------------------------------------------------------------------


def test_receive_stock_non_batch_tracked(world):
    db, company, wh1, plain_prod = (
        world["db"],
        world["company"],
        world["wh1"],
        world["plain_prod"],
    )
    mv = _recv(db, company.id, wh1.id, plain_prod.id, qty=100, cost="2.500")
    assert mv.movement_type == MovementType.RECEIPT
    assert mv.quantity == Decimal("100")
    db.refresh(mv)  # total_cost is GENERATED ALWAYS — must read back from Postgres
    assert mv.total_cost == Decimal("100") * Decimal("2.500")

    bal = _bal(db, company.id, wh1.id, plain_prod.id)
    assert bal.quantity_on_hand == Decimal("100")
    assert bal.weighted_avg_cost == Decimal("2.500")


def test_receive_stock_batch_tracked(world):
    db, company, wh1, batch_prod = (
        world["db"],
        world["company"],
        world["wh1"],
        world["batch_prod"],
    )
    batch = _make_batch(db, company.id, batch_prod.id, "B001")
    mv = _recv(db, company.id, wh1.id, batch_prod.id, qty=1000, cost="0.003", batch_id=batch.id)
    assert mv.batch_id == batch.id
    bal = _bal(db, company.id, wh1.id, batch_prod.id, batch_id=batch.id)
    assert bal.quantity_on_hand == Decimal("1000")


def test_receive_requires_batch_id_for_batch_tracked_product(world):
    db, company, wh1, batch_prod = (
        world["db"],
        world["company"],
        world["wh1"],
        world["batch_prod"],
    )
    with pytest.raises(BusinessRuleViolation, match="batch_id is required"):
        _recv(db, company.id, wh1.id, batch_prod.id, qty=10, cost=1)


def test_receive_rejects_batch_id_for_non_batch_tracked(world):
    db, company, wh1, plain_prod, batch_prod = (
        world["db"],
        world["company"],
        world["wh1"],
        world["plain_prod"],
        world["batch_prod"],
    )
    batch = _make_batch(db, company.id, batch_prod.id, "B001")
    with pytest.raises(BusinessRuleViolation, match="not batch-tracked"):
        _recv(db, company.id, wh1.id, plain_prod.id, qty=10, cost=1, batch_id=batch.id)


# ---------------------------------------------------------------------------
# Weighted-average costing
# ---------------------------------------------------------------------------


def test_weighted_average_two_receipts(world):
    """
    Receipt 1: 100 units @ 2.00 => avg = 2.00
    Receipt 2: 200 units @ 3.50 => avg = (100*2 + 200*3.5) / 300 = 900/300 = 3.00
    """
    db, company, wh1, plain_prod = (
        world["db"],
        world["company"],
        world["wh1"],
        world["plain_prod"],
    )
    _recv(db, company.id, wh1.id, plain_prod.id, qty=100, cost="2.00")
    _recv(db, company.id, wh1.id, plain_prod.id, qty=200, cost="3.50")
    bal = _bal(db, company.id, wh1.id, plain_prod.id)
    assert bal.quantity_on_hand == Decimal("300")
    assert bal.weighted_avg_cost == Decimal("3.00")


def test_weighted_average_unchanged_on_issue(world):
    """Issuing stock does not change the weighted average cost."""
    db, company, wh1, plain_prod = (
        world["db"],
        world["company"],
        world["wh1"],
        world["plain_prod"],
    )
    _recv(db, company.id, wh1.id, plain_prod.id, qty=100, cost="5.00")
    _issue(db, company.id, wh1.id, plain_prod.id, qty=30)
    bal = _bal(db, company.id, wh1.id, plain_prod.id)
    assert bal.quantity_on_hand == Decimal("70")
    assert bal.weighted_avg_cost == Decimal("5.00")


# ---------------------------------------------------------------------------
# issue_stock
# ---------------------------------------------------------------------------


def test_issue_stock_reduces_balance(world):
    db, company, wh1, plain_prod = (
        world["db"],
        world["company"],
        world["wh1"],
        world["plain_prod"],
    )
    _recv(db, company.id, wh1.id, plain_prod.id, qty=50, cost=1)
    mv = _issue(db, company.id, wh1.id, plain_prod.id, qty=20)
    assert mv.quantity == Decimal("-20")
    assert _bal(db, company.id, wh1.id, plain_prod.id).quantity_on_hand == Decimal("30")


def test_issue_blocked_when_insufficient_and_negative_not_allowed(world):
    db, company, wh1, plain_prod = (
        world["db"],
        world["company"],
        world["wh1"],
        world["plain_prod"],
    )
    _recv(db, company.id, wh1.id, plain_prod.id, qty=10, cost=1)
    with pytest.raises(BusinessRuleViolation, match="Insufficient stock"):
        _issue(db, company.id, wh1.id, plain_prod.id, qty=50)


def test_issue_allowed_with_company_negative_stock_policy(world):
    db, company, wh1, plain_prod = (
        world["db"],
        world["company"],
        world["wh1"],
        world["plain_prod"],
    )
    service.get_or_create_settings(db, company.id).allow_negative_stock = True
    _recv(db, company.id, wh1.id, plain_prod.id, qty=5, cost=1)
    _issue(db, company.id, wh1.id, plain_prod.id, qty=50)
    assert _bal(db, company.id, wh1.id, plain_prod.id).quantity_on_hand == Decimal("-45")


def test_issue_allowed_with_per_movement_approved_negative(world):
    db, company, wh1, plain_prod = (
        world["db"],
        world["company"],
        world["wh1"],
        world["plain_prod"],
    )
    _issue(db, company.id, wh1.id, plain_prod.id, qty=100, approved=True)
    assert _bal(db, company.id, wh1.id, plain_prod.id).quantity_on_hand == Decimal("-100")


# ---------------------------------------------------------------------------
# transfer_stock
# ---------------------------------------------------------------------------


def test_transfer_creates_two_linked_legs(world):
    db, company, wh1, wh2, plain_prod = (
        world["db"],
        world["company"],
        world["wh1"],
        world["wh2"],
        world["plain_prod"],
    )
    _recv(db, company.id, wh1.id, plain_prod.id, qty=100, cost=4)
    out_mv, in_mv = service.transfer_stock(
        db,
        schemas.TransferStockRequest(
            from_warehouse_id=wh1.id,
            to_warehouse_id=wh2.id,
            product_id=plain_prod.id,
            quantity=Decimal("40"),
        ),
        company_id=company.id,
    )
    assert out_mv.movement_type == MovementType.TRANSFER_OUT
    assert in_mv.movement_type == MovementType.TRANSFER_IN
    assert out_mv.quantity == Decimal("-40")
    assert in_mv.quantity == Decimal("40")
    assert out_mv.reference_id == in_mv.id
    assert in_mv.reference_id == out_mv.id
    assert out_mv.reference_type == "inventory_transfer"
    assert in_mv.reference_type == "inventory_transfer"
    assert _bal(db, company.id, wh1.id, plain_prod.id).quantity_on_hand == Decimal("60")
    assert _bal(db, company.id, wh2.id, plain_prod.id).quantity_on_hand == Decimal("40")


def test_transfer_same_warehouse_rejected(world):
    db, company, wh1, plain_prod = (
        world["db"],
        world["company"],
        world["wh1"],
        world["plain_prod"],
    )
    with pytest.raises(BusinessRuleViolation, match="same warehouse"):
        service.transfer_stock(
            db,
            schemas.TransferStockRequest(
                from_warehouse_id=wh1.id,
                to_warehouse_id=wh1.id,
                product_id=plain_prod.id,
                quantity=Decimal("10"),
            ),
            company_id=company.id,
        )


def test_transfer_insufficient_stock_blocked(world):
    db, company, wh1, wh2, plain_prod = (
        world["db"],
        world["company"],
        world["wh1"],
        world["wh2"],
        world["plain_prod"],
    )
    _recv(db, company.id, wh1.id, plain_prod.id, qty=5, cost=1)
    with pytest.raises(BusinessRuleViolation, match="Insufficient stock"):
        service.transfer_stock(
            db,
            schemas.TransferStockRequest(
                from_warehouse_id=wh1.id,
                to_warehouse_id=wh2.id,
                product_id=plain_prod.id,
                quantity=Decimal("100"),
            ),
            company_id=company.id,
        )


# ---------------------------------------------------------------------------
# adjust_stock
# ---------------------------------------------------------------------------


def test_adjustment_in(world):
    db, company, wh1, plain_prod = (
        world["db"],
        world["company"],
        world["wh1"],
        world["plain_prod"],
    )
    _recv(db, company.id, wh1.id, plain_prod.id, qty=50, cost=2)
    mv = service.adjust_stock(
        db,
        schemas.AdjustStockRequest(
            warehouse_id=wh1.id,
            product_id=plain_prod.id,
            quantity_delta=Decimal("10"),
            unit_cost=Decimal("3"),
        ),
        company_id=company.id,
    )
    assert mv.movement_type == MovementType.ADJUSTMENT_IN
    assert _bal(db, company.id, wh1.id, plain_prod.id).quantity_on_hand == Decimal("60")


def test_adjustment_out(world):
    db, company, wh1, plain_prod = (
        world["db"],
        world["company"],
        world["wh1"],
        world["plain_prod"],
    )
    _recv(db, company.id, wh1.id, plain_prod.id, qty=50, cost=2)
    mv = service.adjust_stock(
        db,
        schemas.AdjustStockRequest(
            warehouse_id=wh1.id,
            product_id=plain_prod.id,
            quantity_delta=Decimal("-5"),
        ),
        company_id=company.id,
    )
    assert mv.movement_type == MovementType.ADJUSTMENT_OUT
    assert _bal(db, company.id, wh1.id, plain_prod.id).quantity_on_hand == Decimal("45")


def test_adjustment_zero_delta_rejected(world):
    db, company, wh1, plain_prod = (
        world["db"],
        world["company"],
        world["wh1"],
        world["plain_prod"],
    )
    with pytest.raises(BusinessRuleViolation, match="cannot be zero"):
        service.adjust_stock(
            db,
            schemas.AdjustStockRequest(
                warehouse_id=wh1.id,
                product_id=plain_prod.id,
                quantity_delta=Decimal("0"),
            ),
            company_id=company.id,
        )


# ---------------------------------------------------------------------------
# reverse_movement
# ---------------------------------------------------------------------------


def test_reverse_simple_receipt(world):
    db, company, wh1, plain_prod = (
        world["db"],
        world["company"],
        world["wh1"],
        world["plain_prod"],
    )
    mv = _recv(db, company.id, wh1.id, plain_prod.id, qty=100, cost=5)
    reversals = service.reverse_movement(db, mv.id, company_id=company.id)
    assert len(reversals) == 1
    rev = reversals[0]
    assert rev.movement_type == MovementType.REVERSAL
    assert rev.quantity == Decimal("-100")
    assert rev.reference_id == mv.id
    assert _bal(db, company.id, wh1.id, plain_prod.id).quantity_on_hand == Decimal("0")


def test_reverse_transfer_reverses_both_legs(world):
    db, company, wh1, wh2, plain_prod = (
        world["db"],
        world["company"],
        world["wh1"],
        world["wh2"],
        world["plain_prod"],
    )
    _recv(db, company.id, wh1.id, plain_prod.id, qty=100, cost=4)
    out_mv, _ = service.transfer_stock(
        db,
        schemas.TransferStockRequest(
            from_warehouse_id=wh1.id,
            to_warehouse_id=wh2.id,
            product_id=plain_prod.id,
            quantity=Decimal("40"),
        ),
        company_id=company.id,
    )
    reversals = service.reverse_movement(db, out_mv.id, company_id=company.id)
    assert len(reversals) == 2
    assert all(r.movement_type == MovementType.REVERSAL for r in reversals)
    assert _bal(db, company.id, wh1.id, plain_prod.id).quantity_on_hand == Decimal("100")
    assert _bal(db, company.id, wh2.id, plain_prod.id).quantity_on_hand == Decimal("0")


def test_cannot_reverse_a_reversal(world):
    db, company, wh1, plain_prod = (
        world["db"],
        world["company"],
        world["wh1"],
        world["plain_prod"],
    )
    mv = _recv(db, company.id, wh1.id, plain_prod.id, qty=10, cost=1)
    reversals = service.reverse_movement(db, mv.id, company_id=company.id)
    with pytest.raises(BusinessRuleViolation, match="Cannot reverse a REVERSAL"):
        service.reverse_movement(db, reversals[0].id, company_id=company.id)


def test_reverse_not_found(world):
    db, company = world["db"], world["company"]
    with pytest.raises(NotFoundError):
        service.reverse_movement(db, 9999999, company_id=company.id)


# ---------------------------------------------------------------------------
# FIFO rejection
# ---------------------------------------------------------------------------


def test_fifo_costing_rejected(world):
    db, company, wh1, plain_prod = (
        world["db"],
        world["company"],
        world["wh1"],
        world["plain_prod"],
    )
    service.get_or_create_settings(db, company.id).costing_method = CostingMethod.FIFO
    with pytest.raises(BusinessRuleViolation, match="FIFO costing is not yet implemented"):
        _recv(db, company.id, wh1.id, plain_prod.id, qty=1, cost=1)


# ---------------------------------------------------------------------------
# expiring_soon_batches
# ---------------------------------------------------------------------------


def test_expiring_soon_filters_correctly(world):
    db, company, batch_prod = world["db"], world["company"], world["batch_prod"]
    _make_batch(db, company.id, batch_prod.id, "SOON", days_to_expiry=15)
    _make_batch(db, company.id, batch_prod.id, "LATER", days_to_expiry=60)
    _make_batch(db, company.id, batch_prod.id, "AFTER", days_to_expiry=120)
    expiring = service.expiring_soon_batches(db, company.id, within_days=30)
    numbers = [b.batch_number for b in expiring]
    assert "SOON" in numbers
    assert "LATER" not in numbers
    assert "AFTER" not in numbers


# ---------------------------------------------------------------------------
# suggest_fefo_batches
# ---------------------------------------------------------------------------


def test_fefo_ordering(world):
    db, company, wh1, batch_prod = (
        world["db"],
        world["company"],
        world["wh1"],
        world["batch_prod"],
    )
    b_later = _make_batch(db, company.id, batch_prod.id, "LATER", days_to_expiry=90)
    b_soon = _make_batch(db, company.id, batch_prod.id, "SOON", days_to_expiry=10)

    _recv(db, company.id, wh1.id, batch_prod.id, qty=500, cost=1, batch_id=b_later.id)
    _recv(db, company.id, wh1.id, batch_prod.id, qty=200, cost=1, batch_id=b_soon.id)

    suggestions = service.suggest_fefo_batches(
        db, company.id, wh1.id, batch_prod.id, Decimal("300")
    )
    assert suggestions[0][0].batch_number == "SOON"
    assert suggestions[0][1] == Decimal("200")  # all of SOON taken
    assert suggestions[1][0].batch_number == "LATER"
    assert suggestions[1][1] == Decimal("100")  # remaining 100 from LATER


# ---------------------------------------------------------------------------
# recompute_balance
# ---------------------------------------------------------------------------


def test_recompute_balance_matches_live_balance(world):
    db, company, wh1, plain_prod = (
        world["db"],
        world["company"],
        world["wh1"],
        world["plain_prod"],
    )
    _recv(db, company.id, wh1.id, plain_prod.id, qty=200, cost=3)
    _issue(db, company.id, wh1.id, plain_prod.id, qty=50)
    live = _bal(db, company.id, wh1.id, plain_prod.id)
    recomputed = service.recompute_balance(db, company.id, wh1.id, plain_prod.id, None)
    assert recomputed.quantity_on_hand == live.quantity_on_hand


# ---------------------------------------------------------------------------
# Cross-company isolation
# ---------------------------------------------------------------------------


def test_receive_cross_company_warehouse_rejected(world):
    db, company, plain_prod = world["db"], world["company"], world["plain_prod"]
    co2 = _make_company(db, code="CO2")
    br2 = _make_branch(db, co2.id, "BR2")
    wh_other = _make_warehouse(db, br2.id, "WH_OTHER")

    with pytest.raises(NotFoundError):
        _recv(db, company.id, wh_other.id, plain_prod.id, qty=10, cost=1)
