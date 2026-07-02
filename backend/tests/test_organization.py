import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, StatementError

from app.modules.organization import schemas, service
from app.modules.organization.models import Branch, BranchType, WarehouseType


def _make_company(db, code="ACME"):
    return service.create_company(
        db,
        schemas.CompanyCreate(
            code=code,
            name_en=f"{code} Co",
            name_ar=f"شركة {code}",
            commercial_registration_no=f"CR-{code}",
        ),
    )


def _make_branch(db, company_id, code="B1", branch_type=BranchType.RETAIL):
    return service.create_branch(
        db,
        schemas.BranchCreate(
            company_id=company_id,
            code=code,
            name_en=f"Branch {code}",
            name_ar=f"فرع {code}",
            branch_type=branch_type,
        ),
    )


def _make_warehouse(db, branch_id, code="W1"):
    return service.create_warehouse(
        db,
        schemas.WarehouseCreate(
            branch_id=branch_id,
            code=code,
            name_en=f"Warehouse {code}",
            name_ar=f"مستودع {code}",
            warehouse_type=WarehouseType.GENERAL,
        ),
    )


# --- create ------------------------------------------------------------


def test_create_company(db_session):
    company = _make_company(db_session)
    assert company.id is not None
    assert company.base_currency == "KWD"
    assert company.timezone == "Asia/Kuwait"
    assert company.is_deleted is False


def test_create_branch(db_session):
    company = _make_company(db_session)
    branch = _make_branch(db_session, company.id, branch_type=BranchType.RETAIL)
    assert branch.id is not None
    assert branch.company_id == company.id
    assert branch.branch_type == BranchType.RETAIL


def test_create_warehouse(db_session):
    company = _make_company(db_session)
    branch = _make_branch(db_session, company.id, branch_type=BranchType.BOTH)
    warehouse = _make_warehouse(db_session, branch.id)
    assert warehouse.id is not None
    assert warehouse.branch_id == branch.id


# --- unique constraints (partial, scoped to is_deleted=false) ----------


def test_company_code_unique(db_session):
    _make_company(db_session, code="DUP")
    with pytest.raises(IntegrityError):
        _make_company(db_session, code="DUP")


def test_branch_code_unique_within_company_but_reusable_across_companies(db_session):
    company_a = _make_company(db_session, code="CA")
    company_b = _make_company(db_session, code="CB")

    _make_branch(db_session, company_a.id, code="B1")
    # same code, different company -> allowed
    branch_b = _make_branch(db_session, company_b.id, code="B1")
    assert branch_b.id is not None

    # same code, same company -> rejected
    with pytest.raises(IntegrityError):
        _make_branch(db_session, company_a.id, code="B1")


def test_warehouse_code_unique_within_branch(db_session):
    company = _make_company(db_session, code="WCO")
    branch = _make_branch(db_session, company.id, code="B1", branch_type=BranchType.BOTH)
    _make_warehouse(db_session, branch.id, code="W1")
    with pytest.raises(IntegrityError):
        _make_warehouse(db_session, branch.id, code="W1")


# --- enum enforcement ----------------------------------------------------


def test_branch_type_rejects_invalid_value_via_pydantic():
    with pytest.raises(ValidationError):
        schemas.BranchCreate(
            company_id=1,
            code="X",
            name_en="X",
            name_ar="X",
            branch_type="NOT_A_REAL_TYPE",
        )


def test_branch_type_rejects_invalid_value_at_db_level(db_session):
    company = _make_company(db_session, code="ENUMCO")
    branch = Branch(
        company_id=company.id,
        code="ENB",
        name_en="Enum Branch",
        name_ar="فرع",
        branch_type="NOT_A_REAL_TYPE",  # bypasses Pydantic on purpose to hit the DB layer
    )
    db_session.add(branch)
    with pytest.raises(StatementError):
        db_session.flush()


# --- soft-delete / reversible cascade ------------------------------------


def test_soft_delete_cascades_and_restore_reverses_it(db_session):
    company = _make_company(db_session, code="CASC")
    branch = _make_branch(db_session, company.id, branch_type=BranchType.BOTH)
    warehouse = _make_warehouse(db_session, branch.id)

    service.soft_delete_company(db_session, company.id)
    db_session.refresh(branch)
    db_session.refresh(warehouse)
    assert branch.is_deleted is True and branch.deleted_by_cascade is True
    assert warehouse.is_deleted is True and warehouse.deleted_by_cascade is True

    service.restore_company(db_session, company.id)
    db_session.refresh(branch)
    db_session.refresh(warehouse)
    assert branch.is_deleted is False and branch.deleted_by_cascade is False
    assert warehouse.is_deleted is False and warehouse.deleted_by_cascade is False


def test_restore_company_does_not_restore_independently_deleted_branch(db_session):
    company = _make_company(db_session, code="MIXD")
    branch_a = _make_branch(db_session, company.id, code="A")
    branch_b = _make_branch(db_session, company.id, code="B")

    # Branch A is deleted independently, BEFORE the company-level cascade.
    service.soft_delete_branch(db_session, branch_a.id)
    db_session.refresh(branch_a)
    assert branch_a.deleted_by_cascade is False

    service.soft_delete_company(db_session, company.id)
    db_session.refresh(branch_b)
    assert branch_b.is_deleted is True and branch_b.deleted_by_cascade is True

    service.restore_company(db_session, company.id)
    db_session.refresh(branch_a)
    db_session.refresh(branch_b)

    assert branch_a.is_deleted is True, "independently-deleted branch must stay deleted"
    assert branch_b.is_deleted is False, "cascade-deleted branch must be restored"
