"""add inventory tables: batches, stock_movements (with GENERATED ALWAYS total_cost),
stock_balances, inventory_settings; add products.is_batch_tracked

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamp_cols() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    ]


def _audit_cols() -> list[sa.Column]:
    return [
        sa.Column("created_by", sa.BigInteger, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by", sa.BigInteger, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    ]


def _soft_delete_cols() -> list[sa.Column]:
    return [
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    # 1. Add is_batch_tracked to products
    op.add_column(
        "products",
        sa.Column("is_batch_tracked", sa.Boolean, nullable=False, server_default="false"),
    )

    # 2. inventory_settings (one row per company)
    op.create_table(
        "inventory_settings",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("company_id", sa.BigInteger, sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("costing_method", sa.String(30), nullable=False, server_default="WEIGHTED_AVERAGE"),
        sa.Column("allow_negative_stock", sa.Boolean, nullable=False, server_default="false"),
        *_timestamp_cols(),
        *_audit_cols(),
        sa.CheckConstraint("costing_method = 'WEIGHTED_AVERAGE'", name="ck_inventory_settings_wa_only"),
    )

    # 3. batches
    op.create_table(
        "batches",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("company_id", sa.BigInteger, sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("product_id", sa.BigInteger, sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("batch_number", sa.String(100), nullable=False),
        sa.Column("expiry_date", sa.Date, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        *_timestamp_cols(),
        *_audit_cols(),
        *_soft_delete_cols(),
    )
    op.create_index(
        "uq_batches_company_product_number",
        "batches",
        ["company_id", "product_id", "batch_number"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )

    # 4. stock_movements  (append-only ledger; total_cost GENERATED ALWAYS)
    op.create_table(
        "stock_movements",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("company_id", sa.BigInteger, sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("warehouse_id", sa.BigInteger, sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("product_id", sa.BigInteger, sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("batch_id", sa.BigInteger, sa.ForeignKey("batches.id", ondelete="RESTRICT"), nullable=True, index=True),
        sa.Column("movement_type", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 6), nullable=False),
        # GENERATED ALWAYS column — Postgres owns this; app only reads it.
        sa.Column(
            "total_cost",
            sa.Numeric(18, 6),
            sa.Computed("quantity * unit_cost", persisted=True),
            nullable=False,
        ),
        sa.Column("reference_id", sa.BigInteger, sa.ForeignKey("stock_movements.id", ondelete="RESTRICT"), nullable=True, index=True),
        sa.Column("reference_type", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("approved_negative", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.BigInteger, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )

    # 5. stock_balances (write-through cache)
    op.create_table(
        "stock_balances",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("company_id", sa.BigInteger, sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("warehouse_id", sa.BigInteger, sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("product_id", sa.BigInteger, sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("batch_id", sa.BigInteger, sa.ForeignKey("batches.id", ondelete="RESTRICT"), nullable=True, index=True),
        sa.Column("quantity_on_hand", sa.Numeric(18, 6), nullable=False),
        sa.Column("weighted_avg_cost", sa.Numeric(18, 6), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "uq_stock_balances_no_batch",
        "stock_balances",
        ["company_id", "warehouse_id", "product_id"],
        unique=True,
        postgresql_where=sa.text("batch_id IS NULL"),
    )
    op.create_index(
        "uq_stock_balances_with_batch",
        "stock_balances",
        ["company_id", "warehouse_id", "product_id", "batch_id"],
        unique=True,
        postgresql_where=sa.text("batch_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_table("stock_balances")
    op.drop_table("stock_movements")
    op.drop_table("batches")
    op.drop_table("inventory_settings")
    op.drop_column("products", "is_batch_tracked")
