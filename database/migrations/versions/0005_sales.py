"""Sales module: settings, price lists, approval requests, invoices, credit notes,
collections; add payment_term_days to customers and max_discount_pct to roles.

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
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
    # 1. Extend existing tables
    op.add_column(
        "customers",
        sa.Column(
            "payment_term_days",
            sa.BigInteger,
            nullable=False,
            server_default="30",
        ),
    )
    op.add_column(
        "roles",
        sa.Column(
            "max_discount_pct",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="0.00",
        ),
    )
    op.create_check_constraint(
        "ck_roles_max_discount_pct",
        "roles",
        "max_discount_pct >= 0 AND max_discount_pct <= 100",
    )

    # 2. sales_settings
    op.create_table(
        "sales_settings",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "company_id",
            sa.BigInteger,
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "mixed_terms_policy",
            sa.String(10),
            nullable=False,
            server_default="HIGHEST",
        ),
        sa.Column(
            "allow_sale_to_inactive_customer",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "allow_sale_over_credit_limit",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "allow_negative_stock_on_sale",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "allow_backdated_invoice",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        sa.Column("next_invoice_number", sa.Integer, nullable=False, server_default="1"),
        sa.Column("next_credit_note_number", sa.Integer, nullable=False, server_default="1"),
        sa.Column("next_collection_number", sa.Integer, nullable=False, server_default="1"),
        *_ts(),
        *_audit(),
    )
    op.create_index(
        "uq_sales_settings_company",
        "sales_settings",
        ["company_id"],
        unique=True,
    )

    # 3. price_lists
    op.create_table(
        "price_lists",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "company_id",
            sa.BigInteger,
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name_en", sa.String(200), nullable=False),
        sa.Column("name_ar", sa.String(200), nullable=False),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        *_ts(),
        *_audit(),
        *_soft(),
    )
    op.create_index(
        "uq_price_lists_company_code",
        "price_lists",
        ["company_id", "code"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "uq_price_lists_company_default",
        "price_lists",
        ["company_id"],
        unique=True,
        postgresql_where=sa.text("is_default = true AND is_deleted = false"),
    )

    # 4. price_list_items
    op.create_table(
        "price_list_items",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "price_list_id",
            sa.BigInteger,
            sa.ForeignKey("price_lists.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "product_id",
            sa.BigInteger,
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("unit_price", sa.Numeric(18, 3), nullable=False),
        sa.CheckConstraint("unit_price >= 0", name="ck_price_list_items_price_positive"),
        *_ts(),
        *_audit(),
        *_soft(),
    )
    op.create_index(
        "uq_price_list_items_list_product",
        "price_list_items",
        ["price_list_id", "product_id"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )

    # 5. approval_requests
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "company_id",
            sa.BigInteger,
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("request_type", sa.String(30), nullable=False),
        sa.Column("reference_type", sa.String(50), nullable=False),
        sa.Column("reference_id", sa.BigInteger, nullable=False),
        sa.Column(
            "requested_by",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="PENDING"),
        sa.Column(
            "approved_by",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approval_metadata", sa.Text, nullable=True),
        *_ts(),
        *_audit(),
    )
    op.create_index(
        "ix_approval_requests_ref",
        "approval_requests",
        ["reference_type", "reference_id", "request_type", "status"],
    )

    # 6. sales_invoices
    op.create_table(
        "sales_invoices",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "company_id",
            sa.BigInteger,
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "branch_id",
            sa.BigInteger,
            sa.ForeignKey("branches.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("invoice_number", sa.String(20), nullable=False),
        sa.Column(
            "customer_id",
            sa.BigInteger,
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "salesman_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "price_list_id",
            sa.BigInteger,
            sa.ForeignKey("price_lists.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("payment_terms_type", sa.String(10), nullable=False),
        sa.Column("invoice_date", sa.Date, nullable=False),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("subtotal", sa.Numeric(18, 3), nullable=False, server_default="0"),
        sa.Column("total_discount", sa.Numeric(18, 3), nullable=False, server_default="0"),
        sa.Column("total_tax", sa.Numeric(18, 3), nullable=False, server_default="0"),
        sa.Column("grand_total", sa.Numeric(18, 3), nullable=False, server_default="0"),
        sa.Column("amount_collected", sa.Numeric(18, 3), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.CheckConstraint(
            "due_date IS NULL OR due_date >= invoice_date",
            name="ck_sales_invoices_due_date",
        ),
        sa.CheckConstraint(
            "payment_terms_type IN ('CASH','CREDIT')",
            name="ck_sales_invoices_payment_terms",
        ),
        *_ts(),
        *_audit(),
        *_soft(),
    )
    op.create_index(
        "uq_sales_invoices_company_number",
        "sales_invoices",
        ["company_id", "invoice_number"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )

    # 7. sales_invoice_lines
    op.create_table(
        "sales_invoice_lines",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "invoice_id",
            sa.BigInteger,
            sa.ForeignKey("sales_invoices.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "product_id",
            sa.BigInteger,
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "warehouse_id",
            sa.BigInteger,
            sa.ForeignKey("warehouses.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "batch_id",
            sa.BigInteger,
            sa.ForeignKey("batches.id", ondelete="RESTRICT"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "unit_id",
            sa.BigInteger,
            sa.ForeignKey("units_of_measure.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("quantity_ordered", sa.Numeric(18, 6), nullable=False),
        sa.Column("quantity_delivered", sa.Numeric(18, 6), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 3), nullable=False),
        sa.Column("price_source", sa.String(12), nullable=False),
        sa.Column("line_discount", sa.Numeric(18, 3), nullable=False, server_default="0"),
        sa.Column("line_tax", sa.Numeric(18, 3), nullable=False, server_default="0"),
        sa.Column("line_total", sa.Numeric(18, 3), nullable=False),
        sa.Column(
            "stock_movement_id",
            sa.BigInteger,
            sa.ForeignKey("stock_movements.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.CheckConstraint("quantity_ordered > 0", name="ck_sales_invoice_lines_qty_ordered"),
        sa.CheckConstraint(
            "quantity_delivered > 0", name="ck_sales_invoice_lines_qty_delivered"
        ),
        sa.CheckConstraint("unit_price >= 0", name="ck_sales_invoice_lines_price"),
        sa.CheckConstraint("line_discount >= 0", name="ck_sales_invoice_lines_discount"),
        sa.CheckConstraint("line_tax >= 0", name="ck_sales_invoice_lines_tax"),
        *_ts(),
        *_audit(),
        *_soft(),
    )

    # 8. credit_notes
    op.create_table(
        "credit_notes",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "company_id",
            sa.BigInteger,
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "branch_id",
            sa.BigInteger,
            sa.ForeignKey("branches.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("credit_note_number", sa.String(20), nullable=False),
        sa.Column(
            "original_invoice_id",
            sa.BigInteger,
            sa.ForeignKey("sales_invoices.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "customer_id",
            sa.BigInteger,
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("status", sa.String(12), nullable=False, server_default="DRAFT"),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("credit_note_date", sa.Date, nullable=False),
        sa.Column("subtotal", sa.Numeric(18, 3), nullable=False, server_default="0"),
        sa.Column("total_tax", sa.Numeric(18, 3), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(18, 3), nullable=False, server_default="0"),
        *_ts(),
        *_audit(),
        *_soft(),
    )
    op.create_index(
        "uq_credit_notes_company_number",
        "credit_notes",
        ["company_id", "credit_note_number"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )

    # 9. credit_note_lines
    op.create_table(
        "credit_note_lines",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "credit_note_id",
            sa.BigInteger,
            sa.ForeignKey("credit_notes.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "original_line_id",
            sa.BigInteger,
            sa.ForeignKey("sales_invoice_lines.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "product_id",
            sa.BigInteger,
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "warehouse_id",
            sa.BigInteger,
            sa.ForeignKey("warehouses.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "batch_id",
            sa.BigInteger,
            sa.ForeignKey("batches.id", ondelete="RESTRICT"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "unit_id",
            sa.BigInteger,
            sa.ForeignKey("units_of_measure.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("quantity_returned", sa.Numeric(18, 6), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 3), nullable=False),
        sa.Column("line_total", sa.Numeric(18, 3), nullable=False),
        sa.Column(
            "stock_movement_id",
            sa.BigInteger,
            sa.ForeignKey("stock_movements.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.CheckConstraint("quantity_returned > 0", name="ck_credit_note_lines_qty"),
        *_ts(),
        *_audit(),
        *_soft(),
    )

    # 10. collections
    op.create_table(
        "collections",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "company_id",
            sa.BigInteger,
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "branch_id",
            sa.BigInteger,
            sa.ForeignKey("branches.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("collection_number", sa.String(20), nullable=False),
        sa.Column(
            "customer_id",
            sa.BigInteger,
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "salesman_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("collection_date", sa.Date, nullable=False),
        sa.Column("total_amount", sa.Numeric(18, 3), nullable=False),
        sa.Column("allocation_method", sa.String(6), nullable=False, server_default="AUTO"),
        sa.Column("status", sa.String(10), nullable=False, server_default="DRAFT"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.CheckConstraint("total_amount > 0", name="ck_collections_amount_positive"),
        *_ts(),
        *_audit(),
        *_soft(),
    )
    op.create_index(
        "uq_collections_company_number",
        "collections",
        ["company_id", "collection_number"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )

    # 11. collection_lines
    op.create_table(
        "collection_lines",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "collection_id",
            sa.BigInteger,
            sa.ForeignKey("collections.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "invoice_id",
            sa.BigInteger,
            sa.ForeignKey("sales_invoices.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("amount_allocated", sa.Numeric(18, 3), nullable=False),
        sa.CheckConstraint("amount_allocated > 0", name="ck_collection_lines_amount_positive"),
        *_ts(),
        *_audit(),
    )


def downgrade() -> None:
    op.drop_table("collection_lines")
    op.drop_table("collections")
    op.drop_table("credit_note_lines")
    op.drop_table("credit_notes")
    op.drop_table("sales_invoice_lines")
    op.drop_table("sales_invoices")
    op.drop_table("approval_requests")
    op.drop_table("price_list_items")
    op.drop_table("price_lists")
    op.drop_table("sales_settings")
    op.drop_constraint("ck_roles_max_discount_pct", "roles", type_="check")
    op.drop_column("roles", "max_discount_pct")
    op.drop_column("customers", "payment_term_days")
