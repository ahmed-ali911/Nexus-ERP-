from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleViolation, NotFoundError
from app.modules.master_data.models import Product
from app.modules.organization.models import Warehouse

from . import models, schemas

# --- Internal helpers --------------------------------------------------


def _get_warehouse_company_id(db: Session, warehouse_id: int) -> int:
    """Warehouse has no direct company_id; traverse branch to reach it."""
    wh = db.get(Warehouse, warehouse_id)
    if wh is None or wh.is_deleted:
        raise NotFoundError(f"Warehouse {warehouse_id} not found")
    from app.modules.organization.models import Branch

    branch = db.get(Branch, wh.branch_id)
    if branch is None or branch.is_deleted:
        raise NotFoundError(f"Branch for warehouse {warehouse_id} not found")
    return branch.company_id


def _assert_warehouse_in_company(db: Session, warehouse_id: int, company_id: int) -> None:
    wh_company_id = _get_warehouse_company_id(db, warehouse_id)
    if wh_company_id != company_id:
        raise NotFoundError(f"Warehouse {warehouse_id} not found")


def _assert_product_in_company(db: Session, product_id: int, company_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None or product.company_id != company_id or product.is_deleted:
        raise NotFoundError(f"Product {product_id} not found")
    return product


def _assert_batch_valid(
    db: Session, batch_id: int | None, product: Product, company_id: int
) -> models.Batch | None:
    if batch_id is None:
        if product.is_batch_tracked:
            raise BusinessRuleViolation(
                f"Product {product.code} is batch-tracked; batch_id is required"
            )
        return None

    if not product.is_batch_tracked:
        raise BusinessRuleViolation(
            f"Product {product.code} is not batch-tracked; batch_id must be null"
        )
    batch = db.get(models.Batch, batch_id)
    if (
        batch is None
        or batch.product_id != product.id
        or batch.company_id != company_id
        or batch.is_deleted
    ):
        raise NotFoundError(f"Batch {batch_id} not found for product {product.id}")
    return batch


def get_or_create_settings(db: Session, company_id: int) -> models.InventorySettings:
    stmt = select(models.InventorySettings).where(models.InventorySettings.company_id == company_id)
    settings = db.scalars(stmt).first()
    if settings is None:
        settings = models.InventorySettings(
            company_id=company_id,
            costing_method=models.CostingMethod.WEIGHTED_AVERAGE,
            allow_negative_stock=False,
        )
        db.add(settings)
        db.flush()
    return settings


def _get_balance(
    db: Session, company_id: int, warehouse_id: int, product_id: int, batch_id: int | None
) -> models.StockBalance | None:
    if batch_id is None:
        stmt = select(models.StockBalance).where(
            models.StockBalance.company_id == company_id,
            models.StockBalance.warehouse_id == warehouse_id,
            models.StockBalance.product_id == product_id,
            models.StockBalance.batch_id.is_(None),
        )
    else:
        stmt = select(models.StockBalance).where(
            models.StockBalance.company_id == company_id,
            models.StockBalance.warehouse_id == warehouse_id,
            models.StockBalance.product_id == product_id,
            models.StockBalance.batch_id == batch_id,
        )
    return db.scalars(stmt).first()


def _update_balance(
    db: Session,
    company_id: int,
    warehouse_id: int,
    product_id: int,
    batch_id: int | None,
    quantity_delta: Decimal,
    unit_cost: Decimal,
    settings: models.InventorySettings,
    approved_negative: bool = False,
) -> models.StockBalance:
    """Apply quantity_delta to the balance cache using weighted-average costing.

    unit_cost is only meaningful when quantity_delta > 0 (receiving stock).
    For outbound movements the existing weighted_avg_cost is preserved.

    Weighted-average formula when receiving:
        new_avg = (old_qty * old_avg + delta_qty * unit_cost) / new_qty

    When old_qty is negative and a receipt arrives the formula still runs but
    the accounting meaning is undefined — we apply it anyway and document the
    tension in comments. See design notes.
    """
    balance = _get_balance(db, company_id, warehouse_id, product_id, batch_id)

    if balance is None:
        # First movement for this slot: create the balance row.
        new_qty = quantity_delta
        if new_qty < 0 and not (settings.allow_negative_stock or approved_negative):
            raise BusinessRuleViolation(
                f"Insufficient stock for product {product_id} in warehouse {warehouse_id}"
            )
        new_avg = unit_cost if quantity_delta > 0 else Decimal(0)
        balance = models.StockBalance(
            company_id=company_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            batch_id=batch_id,
            quantity_on_hand=new_qty,
            weighted_avg_cost=new_avg,
            updated_at=datetime.datetime.now(datetime.UTC),
        )
        db.add(balance)
        db.flush()
        return balance

    old_qty = balance.quantity_on_hand
    old_avg = balance.weighted_avg_cost
    new_qty = old_qty + quantity_delta

    if new_qty < 0 and not settings.allow_negative_stock:
        raise BusinessRuleViolation(
            f"Insufficient stock for product {product_id} in warehouse {warehouse_id}: "
            f"on_hand={old_qty}, requested={abs(quantity_delta)}"
        )

    if quantity_delta > 0:
        # Receiving: recompute weighted average.
        # If old_qty <= 0 we still run the formula; the cost meaning is approximate
        # when old_qty is negative (documented tension, not solved here).
        denom = old_qty + quantity_delta
        if denom == 0:
            new_avg = unit_cost
        else:
            new_avg = (old_qty * old_avg + quantity_delta * unit_cost) / denom
    else:
        # Issuing: keep the current average (it doesn't change when stock leaves).
        new_avg = old_avg

    balance.quantity_on_hand = new_qty
    balance.weighted_avg_cost = new_avg
    balance.updated_at = datetime.datetime.now(datetime.UTC)
    db.flush()
    return balance


def _post_movement(
    db: Session,
    company_id: int,
    warehouse_id: int,
    product_id: int,
    batch_id: int | None,
    movement_type: models.MovementType,
    quantity: Decimal,
    unit_cost: Decimal,
    actor_id: int | None,
    notes: str | None = None,
    reference_id: int | None = None,
    reference_type: str | None = None,
    approved_negative: bool = False,
) -> models.StockMovement:
    """Insert one ledger row. total_cost is GENERATED ALWAYS — do not pass it."""
    movement = models.StockMovement(
        company_id=company_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
        batch_id=batch_id,
        movement_type=movement_type,
        quantity=quantity,
        unit_cost=unit_cost,
        reference_id=reference_id,
        reference_type=reference_type,
        notes=notes,
        approved_negative=approved_negative,
        created_by=actor_id,
    )
    db.add(movement)
    db.flush()
    return movement


# --- Public API --------------------------------------------------------


def receive_stock(
    db: Session,
    payload: schemas.ReceiveStockRequest,
    company_id: int,
    actor_id: int | None = None,
) -> models.StockMovement:
    _assert_warehouse_in_company(db, payload.warehouse_id, company_id)
    product = _assert_product_in_company(db, payload.product_id, company_id)
    _assert_batch_valid(db, payload.batch_id, product, company_id)

    settings = get_or_create_settings(db, company_id)
    if settings.costing_method == models.CostingMethod.FIFO:
        raise BusinessRuleViolation("FIFO costing is not yet implemented; use WEIGHTED_AVERAGE")

    movement = _post_movement(
        db,
        company_id=company_id,
        warehouse_id=payload.warehouse_id,
        product_id=payload.product_id,
        batch_id=payload.batch_id,
        movement_type=models.MovementType.RECEIPT,
        quantity=payload.quantity,
        unit_cost=payload.unit_cost,
        actor_id=actor_id,
        notes=payload.notes,
    )
    _update_balance(
        db,
        company_id=company_id,
        warehouse_id=payload.warehouse_id,
        product_id=payload.product_id,
        batch_id=payload.batch_id,
        quantity_delta=payload.quantity,
        unit_cost=payload.unit_cost,
        settings=settings,
    )
    return movement


def issue_stock(
    db: Session,
    payload: schemas.IssueStockRequest,
    company_id: int,
    actor_id: int | None = None,
) -> models.StockMovement:
    _assert_warehouse_in_company(db, payload.warehouse_id, company_id)
    product = _assert_product_in_company(db, payload.product_id, company_id)
    _assert_batch_valid(db, payload.batch_id, product, company_id)

    settings = get_or_create_settings(db, company_id)

    balance = _get_balance(
        db, company_id, payload.warehouse_id, payload.product_id, payload.batch_id
    )
    current_qty = balance.quantity_on_hand if balance else Decimal(0)
    current_cost = balance.weighted_avg_cost if balance else Decimal(0)

    if current_qty - payload.quantity < 0 and not (
        settings.allow_negative_stock or payload.approved_negative
    ):
        raise BusinessRuleViolation(
            f"Insufficient stock: on_hand={current_qty}, requested={payload.quantity}"
        )

    movement = _post_movement(
        db,
        company_id=company_id,
        warehouse_id=payload.warehouse_id,
        product_id=payload.product_id,
        batch_id=payload.batch_id,
        movement_type=models.MovementType.ISSUE,
        quantity=-payload.quantity,  # negative = leaving warehouse
        unit_cost=current_cost,
        actor_id=actor_id,
        notes=payload.notes,
        approved_negative=payload.approved_negative,
    )
    _update_balance(
        db,
        company_id=company_id,
        warehouse_id=payload.warehouse_id,
        product_id=payload.product_id,
        batch_id=payload.batch_id,
        quantity_delta=-payload.quantity,
        unit_cost=current_cost,
        settings=settings,
        approved_negative=payload.approved_negative,
    )
    return movement


def transfer_stock(
    db: Session,
    payload: schemas.TransferStockRequest,
    company_id: int,
    actor_id: int | None = None,
) -> tuple[models.StockMovement, models.StockMovement]:
    """Returns (transfer_out_movement, transfer_in_movement)."""
    if payload.from_warehouse_id == payload.to_warehouse_id:
        raise BusinessRuleViolation("Cannot transfer stock to the same warehouse")

    _assert_warehouse_in_company(db, payload.from_warehouse_id, company_id)
    _assert_warehouse_in_company(db, payload.to_warehouse_id, company_id)
    product = _assert_product_in_company(db, payload.product_id, company_id)
    _assert_batch_valid(db, payload.batch_id, product, company_id)

    settings = get_or_create_settings(db, company_id)

    balance = _get_balance(
        db, company_id, payload.from_warehouse_id, payload.product_id, payload.batch_id
    )
    current_qty = balance.quantity_on_hand if balance else Decimal(0)
    current_cost = balance.weighted_avg_cost if balance else Decimal(0)

    if current_qty - payload.quantity < 0 and not (
        settings.allow_negative_stock or payload.approved_negative
    ):
        raise BusinessRuleViolation(
            f"Insufficient stock for transfer: on_hand={current_qty}, requested={payload.quantity}"
        )

    # Post TRANSFER_OUT first (no reference_id yet — we need the IN row's id).
    out_movement = _post_movement(
        db,
        company_id=company_id,
        warehouse_id=payload.from_warehouse_id,
        product_id=payload.product_id,
        batch_id=payload.batch_id,
        movement_type=models.MovementType.TRANSFER_OUT,
        quantity=-payload.quantity,
        unit_cost=current_cost,
        actor_id=actor_id,
        notes=payload.notes,
        approved_negative=payload.approved_negative,
    )

    # Post TRANSFER_IN and link both legs via reference_id.
    in_movement = _post_movement(
        db,
        company_id=company_id,
        warehouse_id=payload.to_warehouse_id,
        product_id=payload.product_id,
        batch_id=payload.batch_id,
        movement_type=models.MovementType.TRANSFER_IN,
        quantity=payload.quantity,
        unit_cost=current_cost,
        actor_id=actor_id,
        notes=payload.notes,
        reference_id=out_movement.id,
        reference_type="inventory_transfer",
    )

    # Back-link: update OUT movement to reference IN.
    out_movement.reference_id = in_movement.id
    out_movement.reference_type = "inventory_transfer"
    db.flush()

    _update_balance(
        db,
        company_id=company_id,
        warehouse_id=payload.from_warehouse_id,
        product_id=payload.product_id,
        batch_id=payload.batch_id,
        quantity_delta=-payload.quantity,
        unit_cost=current_cost,
        settings=settings,
    )
    _update_balance(
        db,
        company_id=company_id,
        warehouse_id=payload.to_warehouse_id,
        product_id=payload.product_id,
        batch_id=payload.batch_id,
        quantity_delta=payload.quantity,
        unit_cost=current_cost,
        settings=settings,
    )

    return out_movement, in_movement


def adjust_stock(
    db: Session,
    payload: schemas.AdjustStockRequest,
    company_id: int,
    actor_id: int | None = None,
) -> models.StockMovement:
    if payload.quantity_delta == 0:
        raise BusinessRuleViolation("Adjustment quantity_delta cannot be zero")

    _assert_warehouse_in_company(db, payload.warehouse_id, company_id)
    product = _assert_product_in_company(db, payload.product_id, company_id)
    _assert_batch_valid(db, payload.batch_id, product, company_id)

    settings = get_or_create_settings(db, company_id)

    balance = _get_balance(
        db, company_id, payload.warehouse_id, payload.product_id, payload.batch_id
    )
    current_cost = balance.weighted_avg_cost if balance else Decimal(0)

    movement_type = (
        models.MovementType.ADJUSTMENT_IN
        if payload.quantity_delta > 0
        else models.MovementType.ADJUSTMENT_OUT
    )
    unit_cost = payload.unit_cost if payload.unit_cost is not None else current_cost

    movement = _post_movement(
        db,
        company_id=company_id,
        warehouse_id=payload.warehouse_id,
        product_id=payload.product_id,
        batch_id=payload.batch_id,
        movement_type=movement_type,
        quantity=payload.quantity_delta,
        unit_cost=unit_cost,
        actor_id=actor_id,
        notes=payload.notes,
        approved_negative=payload.approved_negative,
    )
    _update_balance(
        db,
        company_id=company_id,
        warehouse_id=payload.warehouse_id,
        product_id=payload.product_id,
        batch_id=payload.batch_id,
        quantity_delta=payload.quantity_delta,
        unit_cost=unit_cost,
        settings=settings,
    )

    # Accounting: DR/CR Inventory vs Adjustment account (atomic with stock movement)
    import datetime as _dt
    from app.modules.accounting.integration import (
        PostingEvent, SourceModule, event_publisher, get_default_accounts,
    )
    defaults = get_default_accounts(db, company_id)
    if defaults is not None:
        adj_cost = movement.quantity * movement.unit_cost  # positive for IN, negative for OUT
        if adj_cost > 0:
            event_publisher.publish(db, PostingEvent(
                event_type="INVENTORY_ADJUSTMENT_IN",
                source_module=SourceModule.INVENTORY,
                payload={
                    "inventory_account":  defaults["inventory"],
                    "adjustment_account": defaults["inventory_adjustment"],
                    "adjustment_cost":    str(adj_cost),
                },
                entry_date=_dt.date.today(),
                company_id=company_id,
                actor_id=actor_id,
                idempotency_key=f"inv_adjustment_{movement.id}",
            ))
        elif adj_cost < 0:
            event_publisher.publish(db, PostingEvent(
                event_type="INVENTORY_ADJUSTMENT_OUT",
                source_module=SourceModule.INVENTORY,
                payload={
                    "adjustment_account": defaults["inventory_adjustment"],
                    "inventory_account":  defaults["inventory"],
                    "adjustment_cost":    str(-adj_cost),  # positive amount
                },
                entry_date=_dt.date.today(),
                company_id=company_id,
                actor_id=actor_id,
                idempotency_key=f"inv_adjustment_{movement.id}",
            ))

    return movement


def reverse_movement(
    db: Session,
    movement_id: int,
    company_id: int,
    actor_id: int | None = None,
    notes: str | None = None,
) -> list[models.StockMovement]:
    """Reverse a prior movement (or both legs of a transfer atomically).
    Returns the list of REVERSAL rows posted.
    """
    original = db.get(models.StockMovement, movement_id)
    if original is None or original.company_id != company_id:
        raise NotFoundError(f"StockMovement {movement_id} not found")

    if original.movement_type == models.MovementType.REVERSAL:
        raise BusinessRuleViolation("Cannot reverse a REVERSAL movement")

    settings = get_or_create_settings(db, company_id)

    def _post_reversal(src: models.StockMovement) -> models.StockMovement:
        reversal = _post_movement(
            db,
            company_id=src.company_id,
            warehouse_id=src.warehouse_id,
            product_id=src.product_id,
            batch_id=src.batch_id,
            movement_type=models.MovementType.REVERSAL,
            quantity=-src.quantity,  # opposite sign cancels the original
            unit_cost=src.unit_cost,
            actor_id=actor_id,
            notes=notes or f"Reversal of movement {src.id}",
            reference_id=src.id,
            reference_type="reversal",
        )
        _update_balance(
            db,
            company_id=src.company_id,
            warehouse_id=src.warehouse_id,
            product_id=src.product_id,
            batch_id=src.batch_id,
            quantity_delta=-src.quantity,
            unit_cost=src.unit_cost,
            settings=settings,
        )
        return reversal

    reversals: list[models.StockMovement] = [_post_reversal(original)]

    # If this is a transfer leg, reverse the sibling leg too.
    if original.reference_type == "inventory_transfer" and original.reference_id is not None:
        sibling = db.get(models.StockMovement, original.reference_id)
        if sibling is not None and sibling.movement_type != models.MovementType.REVERSAL:
            reversals.append(_post_reversal(sibling))

    return reversals


def recompute_balance(
    db: Session,
    company_id: int,
    warehouse_id: int,
    product_id: int,
    batch_id: int | None,
) -> models.StockBalance:
    """Full replay of the ledger for a given slot. Used for reconciliation.
    Warning: expensive on large ledgers; call from a background job, not an HTTP request.
    """
    stmt = (
        select(models.StockMovement)
        .where(
            models.StockMovement.company_id == company_id,
            models.StockMovement.warehouse_id == warehouse_id,
            models.StockMovement.product_id == product_id,
        )
        .order_by(models.StockMovement.id)
    )
    if batch_id is None:
        stmt = stmt.where(models.StockMovement.batch_id.is_(None))
    else:
        stmt = stmt.where(models.StockMovement.batch_id == batch_id)

    movements = list(db.scalars(stmt))

    qty = Decimal(0)
    avg_cost = Decimal(0)
    for m in movements:
        delta = m.quantity
        new_qty = qty + delta
        if delta > 0:
            denom = new_qty
            avg_cost = (qty * avg_cost + delta * m.unit_cost) / denom if denom != 0 else m.unit_cost
        qty = new_qty

    balance = _get_balance(db, company_id, warehouse_id, product_id, batch_id)
    if balance is None:
        balance = models.StockBalance(
            company_id=company_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            batch_id=batch_id,
            quantity_on_hand=qty,
            weighted_avg_cost=avg_cost,
            updated_at=datetime.datetime.now(datetime.UTC),
        )
        db.add(balance)
    else:
        balance.quantity_on_hand = qty
        balance.weighted_avg_cost = avg_cost
        balance.updated_at = datetime.datetime.now(datetime.UTC)

    db.flush()
    return balance


# --- Batch CRUD ----------------------------------------------------------


def create_batch(
    db: Session, payload: schemas.BatchCreate, company_id: int, actor_id: int | None = None
) -> models.Batch:
    product = _assert_product_in_company(db, payload.product_id, company_id)
    if not product.is_batch_tracked:
        raise BusinessRuleViolation(
            f"Product {product.code} is not batch-tracked; cannot create a batch for it"
        )
    batch = models.Batch(
        company_id=company_id,
        product_id=payload.product_id,
        batch_number=payload.batch_number,
        expiry_date=payload.expiry_date,
        notes=payload.notes,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(batch)
    db.flush()
    return batch


def get_batch(db: Session, batch_id: int) -> models.Batch:
    batch = db.get(models.Batch, batch_id)
    if batch is None:
        raise NotFoundError(f"Batch {batch_id} not found")
    return batch


def list_batches(
    db: Session,
    company_id: int,
    product_id: int | None = None,
    include_deleted: bool = False,
) -> list[models.Batch]:
    stmt = select(models.Batch).where(models.Batch.company_id == company_id)
    if product_id is not None:
        stmt = stmt.where(models.Batch.product_id == product_id)
    if not include_deleted:
        stmt = stmt.where(models.Batch.is_deleted.is_(False))
    return list(db.scalars(stmt.order_by(models.Batch.id)))


def list_balances(
    db: Session,
    company_id: int,
    warehouse_id: int | None = None,
    product_id: int | None = None,
) -> list[models.StockBalance]:
    stmt = select(models.StockBalance).where(models.StockBalance.company_id == company_id)
    if warehouse_id is not None:
        stmt = stmt.where(models.StockBalance.warehouse_id == warehouse_id)
    if product_id is not None:
        stmt = stmt.where(models.StockBalance.product_id == product_id)
    return list(
        db.scalars(stmt.order_by(models.StockBalance.warehouse_id, models.StockBalance.product_id))
    )


def list_movements(
    db: Session,
    company_id: int,
    warehouse_id: int | None = None,
    product_id: int | None = None,
) -> list[models.StockMovement]:
    stmt = select(models.StockMovement).where(models.StockMovement.company_id == company_id)
    if warehouse_id is not None:
        stmt = stmt.where(models.StockMovement.warehouse_id == warehouse_id)
    if product_id is not None:
        stmt = stmt.where(models.StockMovement.product_id == product_id)
    return list(db.scalars(stmt.order_by(models.StockMovement.id)))


def expiring_soon_batches(
    db: Session, company_id: int, within_days: int = 30
) -> list[models.Batch]:
    """Return active batches expiring within `within_days` days from today."""
    cutoff = datetime.date.today() + datetime.timedelta(days=within_days)
    stmt = (
        select(models.Batch)
        .where(
            models.Batch.company_id == company_id,
            models.Batch.is_deleted.is_(False),
            models.Batch.expiry_date.isnot(None),
            models.Batch.expiry_date <= cutoff,
        )
        .order_by(models.Batch.expiry_date)
    )
    return list(db.scalars(stmt))


def suggest_fefo_batches(
    db: Session,
    company_id: int,
    warehouse_id: int,
    product_id: int,
    quantity_needed: Decimal,
) -> list[tuple[models.Batch, Decimal]]:
    """FEFO (First Expiry First Out) batch suggestion.
    Returns [(batch, qty_to_take)] in expiry order covering quantity_needed.
    """
    stmt = (
        select(models.Batch)
        .where(
            models.Batch.company_id == company_id,
            models.Batch.product_id == product_id,
            models.Batch.is_deleted.is_(False),
        )
        .order_by(models.Batch.expiry_date.nulls_last(), models.Batch.id)
    )
    batches = list(db.scalars(stmt))

    result: list[tuple[models.Batch, Decimal]] = []
    remaining = quantity_needed
    for batch in batches:
        if remaining <= 0:
            break
        balance = _get_balance(db, company_id, warehouse_id, product_id, batch.id)
        available = balance.quantity_on_hand if balance else Decimal(0)
        if available <= 0:
            continue
        take = min(available, remaining)
        result.append((batch, take))
        remaining -= take

    return result
