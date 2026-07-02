from __future__ import annotations

import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError

from . import models, schemas

# --- Companies -----------------------------------------------------------


def create_company(
    db: Session, payload: schemas.CompanyCreate, actor_id: int | None = None
) -> models.Company:
    company = models.Company(**payload.model_dump(), created_by=actor_id, updated_by=actor_id)
    db.add(company)
    db.flush()
    return company


def get_company(db: Session, company_id: int) -> models.Company:
    company = db.get(models.Company, company_id)
    if company is None:
        raise NotFoundError(f"Company {company_id} not found")
    return company


def list_companies(db: Session, include_deleted: bool = False) -> list[models.Company]:
    stmt = select(models.Company)
    if not include_deleted:
        stmt = stmt.where(models.Company.is_deleted.is_(False))
    return list(db.scalars(stmt.order_by(models.Company.id)))


def update_company(
    db: Session, company_id: int, payload: schemas.CompanyUpdate, actor_id: int | None = None
) -> models.Company:
    company = get_company(db, company_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(company, field, value)
    company.updated_by = actor_id
    db.flush()
    return company


def soft_delete_company(
    db: Session, company_id: int, actor_id: int | None = None
) -> models.Company:
    company = get_company(db, company_id)
    if company.is_deleted:
        return company

    now = datetime.datetime.now(datetime.UTC)
    company.is_deleted = True
    company.deleted_at = now
    company.updated_by = actor_id

    branches = db.scalars(
        select(models.Branch).where(
            models.Branch.company_id == company.id, models.Branch.is_deleted.is_(False)
        )
    )
    for branch in branches:
        _soft_delete_branch(db, branch, actor_id, cascade=True, now=now)

    db.flush()
    return company


def restore_company(db: Session, company_id: int, actor_id: int | None = None) -> models.Company:
    company = get_company(db, company_id)
    if not company.is_deleted:
        return company

    company.is_deleted = False
    company.deleted_at = None
    company.updated_by = actor_id

    branches = db.scalars(
        select(models.Branch).where(
            models.Branch.company_id == company.id,
            models.Branch.is_deleted.is_(True),
            models.Branch.deleted_by_cascade.is_(True),
        )
    )
    for branch in branches:
        _restore_branch(db, branch, actor_id)

    db.flush()
    return company


# --- Branches --------------------------------------------------------------


def create_branch(
    db: Session, payload: schemas.BranchCreate, actor_id: int | None = None
) -> models.Branch:
    get_company(db, payload.company_id)  # raises NotFoundError if missing
    branch = models.Branch(**payload.model_dump(), created_by=actor_id, updated_by=actor_id)
    db.add(branch)
    db.flush()
    return branch


def get_branch(db: Session, branch_id: int) -> models.Branch:
    branch = db.get(models.Branch, branch_id)
    if branch is None:
        raise NotFoundError(f"Branch {branch_id} not found")
    return branch


def list_branches(
    db: Session, company_id: int | None = None, include_deleted: bool = False
) -> list[models.Branch]:
    stmt = select(models.Branch)
    if company_id is not None:
        stmt = stmt.where(models.Branch.company_id == company_id)
    if not include_deleted:
        stmt = stmt.where(models.Branch.is_deleted.is_(False))
    return list(db.scalars(stmt.order_by(models.Branch.id)))


def update_branch(
    db: Session, branch_id: int, payload: schemas.BranchUpdate, actor_id: int | None = None
) -> models.Branch:
    branch = get_branch(db, branch_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(branch, field, value)
    branch.updated_by = actor_id
    db.flush()
    return branch


def soft_delete_branch(db: Session, branch_id: int, actor_id: int | None = None) -> models.Branch:
    branch = get_branch(db, branch_id)
    _soft_delete_branch(
        db, branch, actor_id, cascade=False, now=datetime.datetime.now(datetime.UTC)
    )
    db.flush()
    return branch


def restore_branch(db: Session, branch_id: int, actor_id: int | None = None) -> models.Branch:
    branch = get_branch(db, branch_id)
    _restore_branch(db, branch, actor_id)
    db.flush()
    return branch


def _soft_delete_branch(
    db: Session,
    branch: models.Branch,
    actor_id: int | None,
    *,
    cascade: bool,
    now: datetime.datetime,
) -> None:
    if branch.is_deleted:
        return
    branch.is_deleted = True
    branch.deleted_at = now
    branch.deleted_by_cascade = cascade
    branch.updated_by = actor_id

    warehouses = db.scalars(
        select(models.Warehouse).where(
            models.Warehouse.branch_id == branch.id, models.Warehouse.is_deleted.is_(False)
        )
    )
    for warehouse in warehouses:
        _soft_delete_warehouse(db, warehouse, actor_id, cascade=True, now=now)


def _restore_branch(db: Session, branch: models.Branch, actor_id: int | None) -> None:
    if not branch.is_deleted:
        return
    branch.is_deleted = False
    branch.deleted_at = None
    branch.deleted_by_cascade = False
    branch.updated_by = actor_id

    warehouses = db.scalars(
        select(models.Warehouse).where(
            models.Warehouse.branch_id == branch.id,
            models.Warehouse.is_deleted.is_(True),
            models.Warehouse.deleted_by_cascade.is_(True),
        )
    )
    for warehouse in warehouses:
        _restore_warehouse(db, warehouse, actor_id)


# --- Warehouses --------------------------------------------------------------


def create_warehouse(
    db: Session, payload: schemas.WarehouseCreate, actor_id: int | None = None
) -> models.Warehouse:
    get_branch(db, payload.branch_id)  # raises NotFoundError if missing
    warehouse = models.Warehouse(**payload.model_dump(), created_by=actor_id, updated_by=actor_id)
    db.add(warehouse)
    db.flush()
    return warehouse


def get_warehouse(db: Session, warehouse_id: int) -> models.Warehouse:
    warehouse = db.get(models.Warehouse, warehouse_id)
    if warehouse is None:
        raise NotFoundError(f"Warehouse {warehouse_id} not found")
    return warehouse


def list_warehouses(
    db: Session, branch_id: int | None = None, include_deleted: bool = False
) -> list[models.Warehouse]:
    stmt = select(models.Warehouse)
    if branch_id is not None:
        stmt = stmt.where(models.Warehouse.branch_id == branch_id)
    if not include_deleted:
        stmt = stmt.where(models.Warehouse.is_deleted.is_(False))
    return list(db.scalars(stmt.order_by(models.Warehouse.id)))


def update_warehouse(
    db: Session, warehouse_id: int, payload: schemas.WarehouseUpdate, actor_id: int | None = None
) -> models.Warehouse:
    warehouse = get_warehouse(db, warehouse_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(warehouse, field, value)
    warehouse.updated_by = actor_id
    db.flush()
    return warehouse


def soft_delete_warehouse(
    db: Session, warehouse_id: int, actor_id: int | None = None
) -> models.Warehouse:
    warehouse = get_warehouse(db, warehouse_id)
    _soft_delete_warehouse(
        db, warehouse, actor_id, cascade=False, now=datetime.datetime.now(datetime.UTC)
    )
    db.flush()
    return warehouse


def restore_warehouse(
    db: Session, warehouse_id: int, actor_id: int | None = None
) -> models.Warehouse:
    warehouse = get_warehouse(db, warehouse_id)
    _restore_warehouse(db, warehouse, actor_id)
    db.flush()
    return warehouse


def _soft_delete_warehouse(
    db: Session,
    warehouse: models.Warehouse,
    actor_id: int | None,
    *,
    cascade: bool,
    now: datetime.datetime,
) -> None:
    if warehouse.is_deleted:
        return
    warehouse.is_deleted = True
    warehouse.deleted_at = now
    warehouse.deleted_by_cascade = cascade
    warehouse.updated_by = actor_id


def _restore_warehouse(db: Session, warehouse: models.Warehouse, actor_id: int | None) -> None:
    if not warehouse.is_deleted:
        return
    warehouse.is_deleted = False
    warehouse.deleted_at = None
    warehouse.deleted_by_cascade = False
    warehouse.updated_by = actor_id
