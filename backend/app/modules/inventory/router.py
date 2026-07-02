from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import require_permission
from app.modules.auth.models import User

from . import schemas, service

router = APIRouter(prefix="/inventory", tags=["inventory"])


# --- Settings -----------------------------------------------------------


@router.get("/settings", response_model=schemas.InventorySettingsResponse)
def get_settings(
    current_user: User = Depends(require_permission("inventory.settings.read")),
    db: Session = Depends(get_db),
):
    return service.get_or_create_settings(db, company_id=current_user.company_id)


@router.patch("/settings", response_model=schemas.InventorySettingsResponse)
def update_settings(
    payload: schemas.InventorySettingsUpdate,
    current_user: User = Depends(require_permission("inventory.settings.update")),
    db: Session = Depends(get_db),
):
    settings = service.get_or_create_settings(db, company_id=current_user.company_id)
    if payload.allow_negative_stock is not None:
        settings.allow_negative_stock = payload.allow_negative_stock
        settings.updated_by = current_user.id
        db.flush()
    return settings


# --- Batches ------------------------------------------------------------


@router.post("/batches", response_model=schemas.BatchResponse, status_code=201)
def create_batch(
    payload: schemas.BatchCreate,
    current_user: User = Depends(require_permission("inventory.batch.create")),
    db: Session = Depends(get_db),
):
    return service.create_batch(
        db, payload, company_id=current_user.company_id, actor_id=current_user.id
    )


@router.get("/batches", response_model=list[schemas.BatchResponse])
def list_batches(
    product_id: int | None = None,
    include_deleted: bool = False,
    current_user: User = Depends(require_permission("inventory.batch.read")),
    db: Session = Depends(get_db),
):
    return service.list_batches(
        db,
        company_id=current_user.company_id,
        product_id=product_id,
        include_deleted=include_deleted,
    )


@router.get("/batches/{batch_id}", response_model=schemas.BatchResponse)
def get_batch(
    batch_id: int,
    current_user: User = Depends(require_permission("inventory.batch.read")),
    db: Session = Depends(get_db),
):
    return service.get_batch(db, batch_id)


@router.get("/batches/expiring-soon", response_model=list[schemas.BatchResponse])
def expiring_soon(
    within_days: int = 30,
    current_user: User = Depends(require_permission("inventory.batch.read")),
    db: Session = Depends(get_db),
):
    return service.expiring_soon_batches(
        db, company_id=current_user.company_id, within_days=within_days
    )


# --- Movements ----------------------------------------------------------


@router.post("/movements/receive", response_model=schemas.StockMovementResponse, status_code=201)
def receive_stock(
    payload: schemas.ReceiveStockRequest,
    current_user: User = Depends(require_permission("inventory.movement.create")),
    db: Session = Depends(get_db),
):
    return service.receive_stock(
        db, payload, company_id=current_user.company_id, actor_id=current_user.id
    )


@router.post("/movements/issue", response_model=schemas.StockMovementResponse, status_code=201)
def issue_stock(
    payload: schemas.IssueStockRequest,
    current_user: User = Depends(require_permission("inventory.movement.create")),
    db: Session = Depends(get_db),
):
    return service.issue_stock(
        db, payload, company_id=current_user.company_id, actor_id=current_user.id
    )


@router.post(
    "/movements/transfer",
    response_model=list[schemas.StockMovementResponse],
    status_code=201,
)
def transfer_stock(
    payload: schemas.TransferStockRequest,
    current_user: User = Depends(require_permission("inventory.movement.create")),
    db: Session = Depends(get_db),
):
    out_mv, in_mv = service.transfer_stock(
        db, payload, company_id=current_user.company_id, actor_id=current_user.id
    )
    return [out_mv, in_mv]


@router.post("/movements/adjust", response_model=schemas.StockMovementResponse, status_code=201)
def adjust_stock(
    payload: schemas.AdjustStockRequest,
    current_user: User = Depends(require_permission("inventory.movement.create")),
    db: Session = Depends(get_db),
):
    return service.adjust_stock(
        db, payload, company_id=current_user.company_id, actor_id=current_user.id
    )


@router.post(
    "/movements/{movement_id}/reverse",
    response_model=list[schemas.StockMovementResponse],
    status_code=201,
)
def reverse_movement(
    movement_id: int,
    current_user: User = Depends(require_permission("inventory.movement.reverse")),
    db: Session = Depends(get_db),
):
    return service.reverse_movement(
        db, movement_id, company_id=current_user.company_id, actor_id=current_user.id
    )


@router.get("/movements", response_model=list[schemas.StockMovementResponse])
def list_movements(
    warehouse_id: int | None = None,
    product_id: int | None = None,
    current_user: User = Depends(require_permission("inventory.movement.read")),
    db: Session = Depends(get_db),
):
    return service.list_movements(
        db,
        company_id=current_user.company_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
    )


# --- Balances -----------------------------------------------------------


@router.get("/balances", response_model=list[schemas.StockBalanceResponse])
def list_balances(
    warehouse_id: int | None = None,
    product_id: int | None = None,
    current_user: User = Depends(require_permission("inventory.balance.read")),
    db: Session = Depends(get_db),
):
    return service.list_balances(
        db,
        company_id=current_user.company_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
    )
