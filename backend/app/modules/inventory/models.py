from __future__ import annotations

import datetime
import decimal
import enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.mixins import AuditMixin, CreatedOnlyMixin, SoftDeleteMixin, TimestampMixin
from app.modules.organization.mixins import CompanyScopedMixin


class CostingMethod(enum.StrEnum):
    WEIGHTED_AVERAGE = "WEIGHTED_AVERAGE"
    FIFO = "FIFO"  # reserved — rejected at runtime if selected


class MovementType(enum.StrEnum):
    RECEIPT = "RECEIPT"
    ISSUE = "ISSUE"
    TRANSFER_OUT = "TRANSFER_OUT"
    TRANSFER_IN = "TRANSFER_IN"
    ADJUSTMENT_IN = "ADJUSTMENT_IN"
    ADJUSTMENT_OUT = "ADJUSTMENT_OUT"
    REVERSAL = "REVERSAL"


class InventorySettings(Base, CompanyScopedMixin, TimestampMixin, AuditMixin):
    """One row per company; created on first access via get_or_create_settings()."""

    __tablename__ = "inventory_settings"
    __table_args__ = (
        CheckConstraint(
            "costing_method = 'WEIGHTED_AVERAGE'",
            name="ck_inventory_settings_wa_only",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    costing_method: Mapped[CostingMethod] = mapped_column(
        SAEnum(
            CostingMethod,
            native_enum=False,
            validate_strings=True,
            length=30,
            name="ck_inventory_settings_costing_method",
        ),
        nullable=False,
        default=CostingMethod.WEIGHTED_AVERAGE,
        server_default="WEIGHTED_AVERAGE",
    )
    allow_negative_stock: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )


class Batch(Base, CompanyScopedMixin, TimestampMixin, AuditMixin, SoftDeleteMixin):
    """Lot/batch for batch-tracked products."""

    __tablename__ = "batches"
    __table_args__ = (
        Index(
            "uq_batches_company_product_number",
            "company_id",
            "product_id",
            "batch_number",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    batch_number: Mapped[str] = mapped_column(String(100), nullable=False)
    expiry_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class StockMovement(Base, CompanyScopedMixin, CreatedOnlyMixin):
    """Append-only ledger. Rows are never updated or soft-deleted.
    To cancel a movement post a REVERSAL row referencing this row's id.
    Transfer legs are linked via reference_type='inventory_transfer' and reference_id
    so that reverse_movement() can reverse both legs atomically.
    """

    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    batch_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("batches.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    movement_type: Mapped[MovementType] = mapped_column(
        SAEnum(
            MovementType,
            native_enum=False,
            validate_strings=True,
            length=20,
            name="ck_stock_movements_movement_type",
        ),
        nullable=False,
    )
    # Signed qty in the product's base unit: positive = entering, negative = leaving.
    quantity: Mapped[decimal.Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit_cost: Mapped[decimal.Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    # GENERATED ALWAYS AS (quantity * unit_cost) — Postgres owns this column.
    # Computed() tells SQLAlchemy to exclude it from INSERT/UPDATE statements.
    total_cost: Mapped[decimal.Decimal] = mapped_column(
        Numeric(18, 6), Computed("quantity * unit_cost", persisted=True), nullable=False
    )
    # For REVERSAL rows: id of the movement being cancelled.
    # For TRANSFER legs: id of the sibling leg (both reversed atomically).
    reference_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("stock_movements.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    reference_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Explicit per-movement negative-stock override (overrides company policy for one row).
    approved_negative: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )


class StockBalance(Base, CompanyScopedMixin):
    """Atomic write-through cache derived from the StockMovement ledger.
    Unique natural key uses two partial indexes to handle nullable batch_id.
    """

    __tablename__ = "stock_balances"
    __table_args__ = (
        Index(
            "uq_stock_balances_no_batch",
            "company_id",
            "warehouse_id",
            "product_id",
            unique=True,
            postgresql_where=text("batch_id IS NULL"),
        ),
        Index(
            "uq_stock_balances_with_batch",
            "company_id",
            "warehouse_id",
            "product_id",
            "batch_id",
            unique=True,
            postgresql_where=text("batch_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    batch_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("batches.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    quantity_on_hand: Mapped[decimal.Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    weighted_avg_cost: Mapped[decimal.Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
