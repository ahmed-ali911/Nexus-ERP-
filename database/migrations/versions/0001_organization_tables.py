"""add organization tables (companies, branches, warehouses)

Revision ID: 0001
Revises:
Create Date: 2026-07-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name_en", sa.String(length=200), nullable=False),
        sa.Column("name_ar", sa.String(length=200), nullable=False),
        sa.Column("commercial_registration_no", sa.String(length=50), nullable=False),
        sa.Column("tax_id", sa.String(length=50), nullable=True),
        sa.Column("base_currency", sa.String(length=3), nullable=False, server_default="KWD"),
        sa.Column("timezone", sa.String(length=50), nullable=False, server_default="Asia/Kuwait"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "uq_companies_code",
        "companies",
        ["code"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "uq_companies_cr_no",
        "companies",
        ["commercial_registration_no"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "branches",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "company_id",
            sa.BigInteger(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name_en", sa.String(length=200), nullable=False),
        sa.Column("name_ar", sa.String(length=200), nullable=False),
        sa.Column("branch_type", sa.String(length=20), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_cascade", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.CheckConstraint("branch_type IN ('FACTORY','RETAIL','BOTH')", name="ck_branches_branch_type"),
    )
    op.create_index("ix_branches_company_id", "branches", ["company_id"])
    op.create_index(
        "uq_branches_company_code",
        "branches",
        ["company_id", "code"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "warehouses",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "branch_id",
            sa.BigInteger(),
            sa.ForeignKey("branches.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name_en", sa.String(length=200), nullable=False),
        sa.Column("name_ar", sa.String(length=200), nullable=False),
        sa.Column("warehouse_type", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_cascade", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.CheckConstraint(
            "warehouse_type IN ('RAW_MATERIAL','FINISHED_GOODS','GENERAL')",
            name="ck_warehouses_warehouse_type",
        ),
    )
    op.create_index("ix_warehouses_branch_id", "warehouses", ["branch_id"])
    op.create_index(
        "uq_warehouses_branch_code",
        "warehouses",
        ["branch_id", "code"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )


def downgrade() -> None:
    op.drop_table("warehouses")
    op.drop_table("branches")
    op.drop_table("companies")
