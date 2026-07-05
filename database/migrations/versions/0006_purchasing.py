"""Purchasing module: supplier columns, purchase_settings, purchase_orders,
goods_receipts, supplier_invoices, purchase_returns, supplier_payments.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _ts() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    ]


def _audit() -> list[sa.Column]:
    return [
        sa.Column(
            "created_by",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_by",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    ]


def _soft() -> list[sa.Column]:
    return [
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    # ------------------------------------------------------------------
    # suppliers — new columns
    # ------------------------------------------------------------------
    op.add_column(
        "suppliers",
        sa.Column(
            "payment_term_days", sa.BigInteger(), nullable=False, server_default="30"
        ),
    )
    op.add_column(
        "suppliers",
        sa.Column("credit_limit", sa.Numeric(18, 3), nullable=True),
    )
    op.add_column(
        "suppliers",
        sa.Column("currency", sa.String(3), nullable=False, server_default="KWD"),
    )
    op.add_column(
        "suppliers",
        sa.Column("tax_profile", sa.String(50), nullable=True),
    )
    op.add_column(
        "suppliers",
        sa.Column("preferred_payment_method", sa.String(50), nullable=True),
    )

    # ------------------------------------------------------------------
    # purchase_settings  (no soft-delete — it's a singleton config row)
    # ------------------------------------------------------------------
    op.create_table(
        "purchase_settings",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "company_id",
            sa.BigInteger(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "purchase_flow_policy",
            sa.String(20),
            nullable=False,
            server_default="DIRECT_RECEIPT",
        ),
        sa.CheckConstraint(
            "purchase_flow_policy IN ('DIRECT_RECEIPT','PO_REQUIRED','THREE_WAY_MATCH')",
            name="ck_purchase_settings_flow_policy",
        ),
        sa.Column(
            "allow_supplier_over_credit_limit",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "allow_backdated_purchase_docs",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "max_price_variance_pct",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="0",
        ),
        sa.CheckConstraint(
            "max_price_variance_pct >= 0 AND max_price_variance_pct <= 100",
            name="ck_purchase_settings_variance_pct",
        ),
        sa.Column("next_po_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("next_grn_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("next_bill_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("next_payment_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("next_return_number", sa.Integer(), nullable=False, server_default="1"),
        *_ts(),
        *_audit(),
    )

    # ------------------------------------------------------------------
    # purchase_orders
    # ------------------------------------------------------------------
    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "company_id",
            sa.BigInteger(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "branch_id",
            sa.BigInteger(),
            sa.ForeignKey("branches.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "supplier_id",
            sa.BigInteger(),
            sa.ForeignKey("suppliers.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("po_number", sa.String(30), nullable=False),
        sa.Column("po_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.CheckConstraint(
            "status IN ('DRAFT','APPROVED','PARTIALLY_RECEIVED','FULLY_RECEIVED','CANCELLED')",
            name="ck_purchase_orders_status",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        *_soft(),
        *_ts(),
        *_audit(),
    )
    op.create_index(
        "uq_purchase_orders_company_number",
        "purchase_orders",
        ["company_id", "po_number"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "purchase_order_lines",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "po_id",
            sa.BigInteger(),
            sa.ForeignKey("purchase_orders.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "product_id",
            sa.BigInteger(),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "unit_id",
            sa.BigInteger(),
            sa.ForeignKey("units_of_measure.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("quantity_ordered", sa.Numeric(18, 6), nullable=False),
        sa.Column(
            "quantity_received", sa.Numeric(18, 6), nullable=False, server_default="0"
        ),
        sa.Column("unit_cost", sa.Numeric(18, 3), nullable=False),
        sa.CheckConstraint("quantity_ordered > 0", name="ck_po_lines_qty_positive"),
        sa.CheckConstraint("unit_cost >= 0", name="ck_po_lines_cost_nonneg"),
        *_soft(),
        *_ts(),
        *_audit(),
    )

    # ------------------------------------------------------------------
    # goods_receipts
    # ------------------------------------------------------------------
    op.create_table(
        "goods_receipts",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "company_id",
            sa.BigInteger(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "branch_id",
            sa.BigInteger(),
            sa.ForeignKey("branches.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "supplier_id",
            sa.BigInteger(),
            sa.ForeignKey("suppliers.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "purchase_order_id",
            sa.BigInteger(),
            sa.ForeignKey("purchase_orders.id", ondelete="RESTRICT"),
            nullable=True,
            index=True,
        ),
        sa.Column("grn_number", sa.String(30), nullable=False),
        sa.Column("receipt_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="DRAFT"),
        sa.CheckConstraint(
            "status IN ('DRAFT','POSTED','CANCELLED')",
            name="ck_goods_receipts_status",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        *_soft(),
        *_ts(),
        *_audit(),
    )
    op.create_index(
        "uq_goods_receipts_company_number",
        "goods_receipts",
        ["company_id", "grn_number"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "goods_receipt_lines",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "grn_id",
            sa.BigInteger(),
            sa.ForeignKey("goods_receipts.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "po_line_id",
            sa.BigInteger(),
            sa.ForeignKey("purchase_order_lines.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "product_id",
            sa.BigInteger(),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "warehouse_id",
            sa.BigInteger(),
            sa.ForeignKey("warehouses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "unit_id",
            sa.BigInteger(),
            sa.ForeignKey("units_of_measure.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("quantity_received", sa.Numeric(18, 6), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 3), nullable=False),
        sa.Column(
            "batch_id",
            sa.BigInteger(),
            sa.ForeignKey("batches.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("batch_number", sa.String(100), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column(
            "stock_movement_id",
            sa.BigInteger(),
            sa.ForeignKey("stock_movements.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.CheckConstraint(
            "quantity_received > 0", name="ck_grn_lines_qty_positive"
        ),
        sa.CheckConstraint("unit_cost >= 0", name="ck_grn_lines_cost_nonneg"),
        *_soft(),
        *_ts(),
        *_audit(),
    )

    # ------------------------------------------------------------------
    # supplier_invoices
    # ------------------------------------------------------------------
    op.create_table(
        "supplier_invoices",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "company_id",
            sa.BigInteger(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "branch_id",
            sa.BigInteger(),
            sa.ForeignKey("branches.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "supplier_id",
            sa.BigInteger(),
            sa.ForeignKey("suppliers.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "goods_receipt_id",
            sa.BigInteger(),
            sa.ForeignKey("goods_receipts.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "purchase_order_id",
            sa.BigInteger(),
            sa.ForeignKey("purchase_orders.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("bill_number", sa.String(30), nullable=False),
        sa.Column("supplier_ref", sa.String(100), nullable=True),
        sa.Column("bill_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="DRAFT"),
        sa.CheckConstraint(
            "status IN ('DRAFT','POSTED','PAID','CANCELLED')",
            name="ck_supplier_invoices_status",
        ),
        sa.CheckConstraint(
            "due_date IS NULL OR due_date >= bill_date",
            name="ck_supplier_invoices_due_date",
        ),
        sa.Column(
            "grand_total", sa.Numeric(18, 3), nullable=False, server_default="0"
        ),
        sa.Column(
            "amount_paid", sa.Numeric(18, 3), nullable=False, server_default="0"
        ),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_soft(),
        *_ts(),
        *_audit(),
    )
    op.create_index(
        "uq_supplier_invoices_company_number",
        "supplier_invoices",
        ["company_id", "bill_number"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "supplier_invoice_lines",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "bill_id",
            sa.BigInteger(),
            sa.ForeignKey("supplier_invoices.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "grn_line_id",
            sa.BigInteger(),
            sa.ForeignKey("goods_receipt_lines.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "product_id",
            sa.BigInteger(),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "unit_id",
            sa.BigInteger(),
            sa.ForeignKey("units_of_measure.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 3), nullable=False),
        sa.Column(
            "cost_adjustment", sa.Numeric(18, 3), nullable=False, server_default="0"
        ),
        sa.Column("line_total", sa.Numeric(18, 3), nullable=False),
        sa.CheckConstraint(
            "quantity > 0", name="ck_supplier_invoice_lines_qty_positive"
        ),
        sa.CheckConstraint(
            "unit_cost >= 0", name="ck_supplier_invoice_lines_cost_nonneg"
        ),
        *_soft(),
        *_ts(),
        *_audit(),
    )

    # ------------------------------------------------------------------
    # purchase_returns
    # ------------------------------------------------------------------
    op.create_table(
        "purchase_returns",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "company_id",
            sa.BigInteger(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "branch_id",
            sa.BigInteger(),
            sa.ForeignKey("branches.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "supplier_id",
            sa.BigInteger(),
            sa.ForeignKey("suppliers.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "original_grn_id",
            sa.BigInteger(),
            sa.ForeignKey("goods_receipts.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("return_number", sa.String(30), nullable=False),
        sa.Column("return_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(8), nullable=False, server_default="DRAFT"),
        sa.CheckConstraint(
            "status IN ('DRAFT','POSTED','CANCELLED')",
            name="ck_purchase_returns_status",
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("total", sa.Numeric(18, 3), nullable=False, server_default="0"),
        *_soft(),
        *_ts(),
        *_audit(),
    )
    op.create_index(
        "uq_purchase_returns_company_number",
        "purchase_returns",
        ["company_id", "return_number"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "purchase_return_lines",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "return_id",
            sa.BigInteger(),
            sa.ForeignKey("purchase_returns.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "original_grn_line_id",
            sa.BigInteger(),
            sa.ForeignKey("goods_receipt_lines.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("quantity_returned", sa.Numeric(18, 6), nullable=False),
        sa.Column("line_total", sa.Numeric(18, 3), nullable=False),
        sa.Column(
            "stock_movement_id",
            sa.BigInteger(),
            sa.ForeignKey("stock_movements.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.CheckConstraint("quantity_returned > 0", name="ck_pr_lines_qty_positive"),
        *_soft(),
        *_ts(),
        *_audit(),
    )

    # ------------------------------------------------------------------
    # supplier_payments
    # ------------------------------------------------------------------
    op.create_table(
        "supplier_payments",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "company_id",
            sa.BigInteger(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "branch_id",
            sa.BigInteger(),
            sa.ForeignKey("branches.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "supplier_id",
            sa.BigInteger(),
            sa.ForeignKey("suppliers.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("payment_number", sa.String(30), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("total_amount", sa.Numeric(18, 3), nullable=False),
        sa.CheckConstraint(
            "total_amount > 0", name="ck_supplier_payments_amount_positive"
        ),
        sa.Column(
            "allocation_method", sa.String(6), nullable=False, server_default="AUTO"
        ),
        sa.CheckConstraint(
            "allocation_method IN ('AUTO','MANUAL')",
            name="ck_supplier_payments_allocation",
        ),
        sa.Column("status", sa.String(10), nullable=False, server_default="DRAFT"),
        sa.CheckConstraint(
            "status IN ('DRAFT','POSTED','CANCELLED')",
            name="ck_supplier_payments_status",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        *_soft(),
        *_ts(),
        *_audit(),
    )
    op.create_index(
        "uq_supplier_payments_company_number",
        "supplier_payments",
        ["company_id", "payment_number"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "supplier_payment_lines",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "payment_id",
            sa.BigInteger(),
            sa.ForeignKey("supplier_payments.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "bill_id",
            sa.BigInteger(),
            sa.ForeignKey("supplier_invoices.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount_applied", sa.Numeric(18, 3), nullable=False),
        sa.CheckConstraint(
            "amount_applied > 0", name="ck_supplier_payment_lines_amount_positive"
        ),
        *_ts(),
        *_audit(),
    )


def downgrade() -> None:
    op.drop_table("supplier_payment_lines")
    op.drop_table("supplier_payments")
    op.drop_table("purchase_return_lines")
    op.drop_table("purchase_returns")
    op.drop_table("supplier_invoice_lines")
    op.drop_table("supplier_invoices")
    op.drop_table("goods_receipt_lines")
    op.drop_table("goods_receipts")
    op.drop_table("purchase_order_lines")
    op.drop_table("purchase_orders")
    op.drop_table("purchase_settings")
    op.drop_column("suppliers", "preferred_payment_method")
    op.drop_column("suppliers", "tax_profile")
    op.drop_column("suppliers", "currency")
    op.drop_column("suppliers", "credit_limit")
    op.drop_column("suppliers", "payment_term_days")
