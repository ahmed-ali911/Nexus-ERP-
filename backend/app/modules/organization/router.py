from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import require_permission
from app.modules.auth.models import User

from . import schemas, service

router = APIRouter(prefix="/organization", tags=["organization"])

# --- Companies -----------------------------------------------------------


@router.post("/companies", response_model=schemas.CompanyResponse, status_code=201)
def create_company(
    payload: schemas.CompanyCreate,
    current_user: User = Depends(require_permission("organization.company.create")),
    db: Session = Depends(get_db),
):
    return service.create_company(db, payload, actor_id=current_user.id)


@router.get("/companies", response_model=list[schemas.CompanyResponse])
def list_companies(
    include_deleted: bool = False,
    current_user: User = Depends(require_permission("organization.company.read")),
    db: Session = Depends(get_db),
):
    return service.list_companies(db, include_deleted=include_deleted)


@router.get("/companies/{company_id}", response_model=schemas.CompanyResponse)
def get_company(
    company_id: int,
    current_user: User = Depends(require_permission("organization.company.read")),
    db: Session = Depends(get_db),
):
    return service.get_company(db, company_id)


@router.patch("/companies/{company_id}", response_model=schemas.CompanyResponse)
def update_company(
    company_id: int,
    payload: schemas.CompanyUpdate,
    current_user: User = Depends(require_permission("organization.company.update")),
    db: Session = Depends(get_db),
):
    return service.update_company(db, company_id, payload, actor_id=current_user.id)


@router.delete("/companies/{company_id}", response_model=schemas.CompanyResponse)
def delete_company(
    company_id: int,
    current_user: User = Depends(require_permission("organization.company.delete")),
    db: Session = Depends(get_db),
):
    return service.soft_delete_company(db, company_id, actor_id=current_user.id)


@router.post("/companies/{company_id}/restore", response_model=schemas.CompanyResponse)
def restore_company(
    company_id: int,
    current_user: User = Depends(require_permission("organization.company.restore")),
    db: Session = Depends(get_db),
):
    return service.restore_company(db, company_id, actor_id=current_user.id)


# --- Branches --------------------------------------------------------------


@router.post("/branches", response_model=schemas.BranchResponse, status_code=201)
def create_branch(
    payload: schemas.BranchCreate,
    current_user: User = Depends(require_permission("organization.branch.create")),
    db: Session = Depends(get_db),
):
    return service.create_branch(db, payload, actor_id=current_user.id)


@router.get("/branches", response_model=list[schemas.BranchResponse])
def list_branches(
    company_id: int | None = None,
    include_deleted: bool = False,
    current_user: User = Depends(require_permission("organization.branch.read")),
    db: Session = Depends(get_db),
):
    return service.list_branches(db, company_id=company_id, include_deleted=include_deleted)


@router.get("/branches/{branch_id}", response_model=schemas.BranchResponse)
def get_branch(
    branch_id: int,
    current_user: User = Depends(require_permission("organization.branch.read")),
    db: Session = Depends(get_db),
):
    return service.get_branch(db, branch_id)


@router.patch("/branches/{branch_id}", response_model=schemas.BranchResponse)
def update_branch(
    branch_id: int,
    payload: schemas.BranchUpdate,
    current_user: User = Depends(require_permission("organization.branch.update")),
    db: Session = Depends(get_db),
):
    return service.update_branch(db, branch_id, payload, actor_id=current_user.id)


@router.delete("/branches/{branch_id}", response_model=schemas.BranchResponse)
def delete_branch(
    branch_id: int,
    current_user: User = Depends(require_permission("organization.branch.delete")),
    db: Session = Depends(get_db),
):
    return service.soft_delete_branch(db, branch_id, actor_id=current_user.id)


@router.post("/branches/{branch_id}/restore", response_model=schemas.BranchResponse)
def restore_branch(
    branch_id: int,
    current_user: User = Depends(require_permission("organization.branch.restore")),
    db: Session = Depends(get_db),
):
    return service.restore_branch(db, branch_id, actor_id=current_user.id)


# --- Warehouses --------------------------------------------------------------


@router.post("/warehouses", response_model=schemas.WarehouseResponse, status_code=201)
def create_warehouse(
    payload: schemas.WarehouseCreate,
    current_user: User = Depends(require_permission("organization.warehouse.create")),
    db: Session = Depends(get_db),
):
    return service.create_warehouse(db, payload, actor_id=current_user.id)


@router.get("/warehouses", response_model=list[schemas.WarehouseResponse])
def list_warehouses(
    branch_id: int | None = None,
    include_deleted: bool = False,
    current_user: User = Depends(require_permission("organization.warehouse.read")),
    db: Session = Depends(get_db),
):
    return service.list_warehouses(db, branch_id=branch_id, include_deleted=include_deleted)


@router.get("/warehouses/{warehouse_id}", response_model=schemas.WarehouseResponse)
def get_warehouse(
    warehouse_id: int,
    current_user: User = Depends(require_permission("organization.warehouse.read")),
    db: Session = Depends(get_db),
):
    return service.get_warehouse(db, warehouse_id)


@router.patch("/warehouses/{warehouse_id}", response_model=schemas.WarehouseResponse)
def update_warehouse(
    warehouse_id: int,
    payload: schemas.WarehouseUpdate,
    current_user: User = Depends(require_permission("organization.warehouse.update")),
    db: Session = Depends(get_db),
):
    return service.update_warehouse(db, warehouse_id, payload, actor_id=current_user.id)


@router.delete("/warehouses/{warehouse_id}", response_model=schemas.WarehouseResponse)
def delete_warehouse(
    warehouse_id: int,
    current_user: User = Depends(require_permission("organization.warehouse.delete")),
    db: Session = Depends(get_db),
):
    return service.soft_delete_warehouse(db, warehouse_id, actor_id=current_user.id)


@router.post("/warehouses/{warehouse_id}/restore", response_model=schemas.WarehouseResponse)
def restore_warehouse(
    warehouse_id: int,
    current_user: User = Depends(require_permission("organization.warehouse.restore")),
    db: Session = Depends(get_db),
):
    return service.restore_warehouse(db, warehouse_id, actor_id=current_user.id)
