"""add master data tables (units, categories, products, conversions, customers, suppliers)

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _mixin_columns() -> list[sa.Column]:
    """created_at/updated_at/created_by/updated_by/is_deleted/deleted_at --
    identical shape on every master-data table (Timestamp+Audit+SoftDelete
    mixins). Built fresh per call since sa.Column objects aren't reusable
    across multiple create_table() calls.
    """
    return [
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "units_of_measure",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "company_id", sa.BigInteger(), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name_en", sa.String(length=100), nullable=False),
        sa.Column("name_ar", sa.String(length=100), nullable=False),
        sa.Column("symbol", sa.String(length=10), nullable=False),
        sa.Column("unit_type", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_mixin_columns(),
        sa.CheckConstraint("unit_type IN ('WEIGHT','COUNT','VOLUME')", name="ck_units_of_measure_unit_type"),
    )
    op.create_index("ix_units_of_measure_company_id", "units_of_measure", ["company_id"])
    op.create_index(
        "uq_units_of_measure_company_code",
        "units_of_measure",
        ["company_id", "code"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "categories",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "company_id", sa.BigInteger(), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name_en", sa.String(length=200), nullable=False),
        sa.Column("name_ar", sa.String(length=200), nullable=False),
        sa.Column(
            "parent_id", sa.BigInteger(), sa.ForeignKey("categories.id", ondelete="RESTRICT"), nullable=True
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_mixin_columns(),
    )
    op.create_index("ix_categories_company_id", "categories", ["company_id"])
    op.create_index("ix_categories_parent_id", "categories", ["parent_id"])
    op.create_index(
        "uq_categories_company_code",
        "categories",
        ["company_id", "code"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "products",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "company_id", sa.BigInteger(), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name_en", sa.String(length=200), nullable=False),
        sa.Column("name_ar", sa.String(length=200), nullable=False),
        sa.Column(
            "category_id", sa.BigInteger(), sa.ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("product_type", sa.String(length=20), nullable=False),
        sa.Column(
            "base_unit_id",
            sa.BigInteger(),
            sa.ForeignKey("units_of_measure.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "purchase_unit_id",
            sa.BigInteger(),
            sa.ForeignKey("units_of_measure.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "sales_unit_id",
            sa.BigInteger(),
            sa.ForeignKey("units_of_measure.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("barcode", sa.String(length=50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_sellable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_purchasable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_stockable", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_mixin_columns(),
        sa.CheckConstraint(
            "product_type IN ('RAW_MATERIAL','SEMI_FINISHED','FINISHED_GOOD')", name="ck_products_product_type"
        ),
    )
    op.create_index("ix_products_company_id", "products", ["company_id"])
    op.create_index("ix_products_category_id", "products", ["category_id"])
    op.create_index("ix_products_base_unit_id", "products", ["base_unit_id"])
    op.create_index(
        "uq_products_company_code",
        "products",
        ["company_id", "code"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "uq_products_company_barcode",
        "products",
        ["company_id", "barcode"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false AND barcode IS NOT NULL"),
    )

    op.create_table(
        "unit_conversions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "company_id", sa.BigInteger(), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "product_id", sa.BigInteger(), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=True
        ),
        sa.Column(
            "from_unit_id",
            sa.BigInteger(),
            sa.ForeignKey("units_of_measure.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "to_unit_id",
            sa.BigInteger(),
            sa.ForeignKey("units_of_measure.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("factor", sa.Numeric(18, 6), nullable=False),
        *_mixin_columns(),
        sa.CheckConstraint("from_unit_id <> to_unit_id", name="ck_unit_conversions_distinct_units"),
        sa.CheckConstraint("factor > 0", name="ck_unit_conversions_factor_positive"),
    )
    op.create_index("ix_unit_conversions_company_id", "unit_conversions", ["company_id"])
    op.create_index("ix_unit_conversions_product_id", "unit_conversions", ["product_id"])
    op.create_index(
        "uq_unit_conversions_universal",
        "unit_conversions",
        ["company_id", "from_unit_id", "to_unit_id"],
        unique=True,
        postgresql_where=sa.text("product_id IS NULL AND is_deleted = false"),
    )
    op.create_index(
        "uq_unit_conversions_product_specific",
        "unit_conversions",
        ["company_id", "product_id", "from_unit_id", "to_unit_id"],
        unique=True,
        postgresql_where=sa.text("product_id IS NOT NULL AND is_deleted = false"),
    )

    op.create_table(
        "customers",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "company_id", sa.BigInteger(), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name_en", sa.String(length=200), nullable=False),
        sa.Column("name_ar", sa.String(length=200), nullable=False),
        sa.Column("customer_type", sa.String(length=20), nullable=False),
        sa.Column("payment_terms", sa.String(length=20), nullable=False),
        sa.Column("credit_limit", sa.Numeric(18, 3), nullable=True),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("tax_id", sa.String(length=50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_mixin_columns(),
        sa.CheckConstraint(
            "customer_type IN ('COMPANY','SHOP','MARKET','INDIVIDUAL')", name="ck_customers_customer_type"
        ),
        sa.CheckConstraint("payment_terms IN ('CASH','CREDIT')", name="ck_customers_payment_terms"),
        sa.CheckConstraint(
            "payment_terms = 'CREDIT' OR credit_limit IS NULL",
            name="ck_customers_credit_limit_requires_credit_terms",
        ),
    )
    op.create_index("ix_customers_company_id", "customers", ["company_id"])
    op.create_index(
        "uq_customers_company_code",
        "customers",
        ["company_id", "code"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "suppliers",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "company_id", sa.BigInteger(), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name_en", sa.String(length=200), nullable=False),
        sa.Column("name_ar", sa.String(length=200), nullable=False),
        sa.Column("supplier_type", sa.String(length=20), nullable=False),
        sa.Column("payment_terms", sa.String(length=20), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("tax_id", sa.String(length=50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_mixin_columns(),
        sa.CheckConstraint("supplier_type IN ('LOCAL','IMPORT')", name="ck_suppliers_supplier_type"),
        sa.CheckConstraint("payment_terms IN ('CASH','CREDIT')", name="ck_suppliers_payment_terms"),
    )
    op.create_index("ix_suppliers_company_id", "suppliers", ["company_id"])
    op.create_index(
        "uq_suppliers_company_code",
        "suppliers",
        ["company_id", "code"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )


def downgrade() -> None:
    op.drop_table("suppliers")
    op.drop_table("customers")
    op.drop_table("unit_conversions")
    op.drop_table("products")
    op.drop_table("categories")
    op.drop_table("units_of_measure")
