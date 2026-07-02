"""add users/roles/permissions/associations, wire audit FKs to users.id

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_AUDIT_FK_TABLES = ("companies", "branches", "warehouses")


def upgrade() -> None:
    # users first -- everything else's audit columns reference it, and it's
    # self-referential (created_by/updated_by -> users.id), which Postgres
    # allows within a single CREATE TABLE.
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "company_id", sa.BigInteger(), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=False),
        sa.Column("full_name_en", sa.String(length=200), nullable=False),
        sa.Column("full_name_ar", sa.String(length=200), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_users_company_id", "users", ["company_id"])
    op.create_index(
        "uq_users_company_username",
        "users",
        ["company_id", "username"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "uq_users_company_email",
        "users",
        ["company_id", "email"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )

    # Now that users exists, wire the deferred audit FKs on the tables from
    # migration 0001 (previously unconstrained nullable BIGINT).
    for table in _AUDIT_FK_TABLES:
        op.create_foreign_key(
            f"fk_{table}_created_by_users", table, "users", ["created_by"], ["id"], ondelete="SET NULL"
        )
        op.create_foreign_key(
            f"fk_{table}_updated_by_users", table, "users", ["updated_by"], ["id"], ondelete="SET NULL"
        )

    op.create_table(
        "roles",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "company_id", sa.BigInteger(), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name_en", sa.String(length=200), nullable=False),
        sa.Column("name_ar", sa.String(length=200), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_roles_company_id", "roles", ["company_id"])
    op.create_index(
        "uq_roles_company_code",
        "roles",
        ["company_id", "code"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )

    op.create_table(
        "permissions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name_en", sa.String(length=200), nullable=False),
        sa.Column("name_ar", sa.String(length=200), nullable=False),
        sa.Column("module", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("code", name="uq_permissions_code"),
    )
    op.create_index("ix_permissions_module", "permissions", ["module"])

    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", sa.BigInteger(), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "assigned_by", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
    )

    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.BigInteger(), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column(
            "permission_id",
            sa.BigInteger(),
            sa.ForeignKey("permissions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.create_table(
        "user_branches",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column(
            "branch_id", sa.BigInteger(), sa.ForeignKey("branches.id", ondelete="CASCADE"), primary_key=True
        ),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_table("refresh_tokens")
    op.drop_table("user_branches")
    op.drop_table("role_permissions")
    op.drop_table("user_roles")
    op.drop_table("permissions")
    op.drop_table("roles")

    for table in _AUDIT_FK_TABLES:
        op.drop_constraint(f"fk_{table}_updated_by_users", table, type_="foreignkey")
        op.drop_constraint(f"fk_{table}_created_by_users", table, type_="foreignkey")

    op.drop_table("users")
