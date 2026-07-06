"""Accounting module: settings, cost_centers, accounts, coa_templates,
coa_template_lines, fiscal_years, accounting_periods, posting_template_headers,
posting_template_lines, journal_entries, journal_entry_lines.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
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
    # 1. accounting_settings
    # ------------------------------------------------------------------
    op.create_table(
        "accounting_settings",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "company_id",
            sa.BigInteger,
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("je_prefix", sa.String(10), nullable=False, server_default="JE"),
        sa.Column("last_je_number", sa.Integer, nullable=False, server_default="0"),
        sa.Column("default_currency", sa.String(3), nullable=False, server_default="KWD"),
        sa.Column(
            "require_manual_je_approval",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "allow_backdated_entries", sa.Boolean, nullable=False, server_default="false"
        ),
        sa.Column("coa_template_code", sa.String(50), nullable=True),
        *_ts(),
        *_audit(),
    )
    op.create_index(
        "uq_accounting_settings_company",
        "accounting_settings",
        ["company_id"],
        unique=True,
    )

    # ------------------------------------------------------------------
    # 2. cost_centers
    # ------------------------------------------------------------------
    op.create_table(
        "cost_centers",
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
        # parent_id — self-referential, added after table creation
        sa.Column("parent_id", sa.BigInteger, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        *_ts(),
        *_audit(),
        *_soft(),
    )
    op.create_foreign_key(
        "fk_cost_centers_parent",
        "cost_centers",
        "cost_centers",
        ["parent_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "uq_cost_centers_company_code",
        "cost_centers",
        ["company_id", "code"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )

    # ------------------------------------------------------------------
    # 3. coa_templates  (system-level, no company_id)
    # ------------------------------------------------------------------
    op.create_table(
        "coa_templates",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name_en", sa.String(200), nullable=False),
        sa.Column("name_ar", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        *_ts(),
        sa.UniqueConstraint("code", name="uq_coa_templates_code"),
    )

    # ------------------------------------------------------------------
    # 4. coa_template_lines
    # ------------------------------------------------------------------
    op.create_table(
        "coa_template_lines",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "template_id",
            sa.BigInteger,
            sa.ForeignKey("coa_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name_en", sa.String(200), nullable=False),
        sa.Column("name_ar", sa.String(200), nullable=False),
        sa.Column("account_type", sa.String(12), nullable=False),
        sa.Column("parent_code", sa.String(20), nullable=True),
        sa.Column("is_postable", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("sequence", sa.Integer, nullable=False, server_default="0"),
        *_ts(),
    )
    op.create_index("ix_coa_tpl_lines_template", "coa_template_lines", ["template_id"])

    # ------------------------------------------------------------------
    # 5. accounts  (Chart of Accounts, company-scoped)
    # ------------------------------------------------------------------
    op.create_table(
        "accounts",
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
        sa.Column("account_type", sa.String(12), nullable=False),
        sa.Column("parent_id", sa.BigInteger, nullable=True),
        sa.Column("is_postable", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("sequence", sa.Integer, nullable=False, server_default="0"),
        *_ts(),
        *_audit(),
        *_soft(),
    )
    op.create_foreign_key(
        "fk_accounts_parent",
        "accounts",
        "accounts",
        ["parent_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "uq_accounts_company_code",
        "accounts",
        ["company_id", "code"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )

    # ------------------------------------------------------------------
    # 6. fiscal_years
    # ------------------------------------------------------------------
    op.create_table(
        "fiscal_years",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "company_id",
            sa.BigInteger,
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name_en", sa.String(100), nullable=False),
        sa.Column("name_ar", sa.String(100), nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column(
            "status", sa.String(10), nullable=False, server_default="OPEN"
        ),
        *_ts(),
        *_audit(),
        *_soft(),
    )
    op.create_index(
        "uq_fiscal_years_company_code",
        "fiscal_years",
        ["company_id", "code"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )

    # ------------------------------------------------------------------
    # 7. accounting_periods
    # ------------------------------------------------------------------
    op.create_table(
        "accounting_periods",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "company_id",
            sa.BigInteger,
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "fiscal_year_id",
            sa.BigInteger,
            sa.ForeignKey("fiscal_years.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("period_no", sa.Integer, nullable=False),
        sa.Column("name_en", sa.String(100), nullable=False),
        sa.Column("name_ar", sa.String(100), nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column(
            "status", sa.String(10), nullable=False, server_default="OPEN"
        ),
        *_ts(),
        *_audit(),
    )
    op.create_index(
        "uq_accounting_periods_company_fy_no",
        "accounting_periods",
        ["company_id", "fiscal_year_id", "period_no"],
        unique=True,
    )

    # ------------------------------------------------------------------
    # 8. posting_template_headers  (company_id NULL = global)
    # ------------------------------------------------------------------
    op.create_table(
        "posting_template_headers",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "company_id",
            sa.BigInteger,
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=True,
            index=True,
        ),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("effective_to", sa.Date, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        *_ts(),
        *_audit(),
        *_soft(),
    )
    op.create_index(
        "uq_posting_tmpl_company_event_ver",
        "posting_template_headers",
        ["company_id", "event_type", "version"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )

    # ------------------------------------------------------------------
    # 9. posting_template_lines
    # ------------------------------------------------------------------
    op.create_table(
        "posting_template_lines",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "header_id",
            sa.BigInteger,
            sa.ForeignKey("posting_template_headers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer, nullable=False, server_default="0"),
        sa.Column("selector_type", sa.String(25), nullable=False),
        sa.Column("selector_param", sa.String(60), nullable=False),
        sa.Column("side", sa.String(6), nullable=False),
        sa.Column("amount_source", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        *_ts(),
    )
    op.create_index(
        "ix_posting_tmpl_lines_header",
        "posting_template_lines",
        ["header_id"],
    )

    # ------------------------------------------------------------------
    # 10. journal_entries  (NO soft delete — immutable)
    # ------------------------------------------------------------------
    op.create_table(
        "journal_entries",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "company_id",
            sa.BigInteger,
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("entry_number", sa.String(30), nullable=False),
        sa.Column("entry_date", sa.Date, nullable=False),
        sa.Column(
            "period_id",
            sa.BigInteger,
            sa.ForeignKey("accounting_periods.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "source_module", sa.String(15), nullable=False, server_default="MANUAL"
        ),
        sa.Column(
            "entry_type", sa.String(12), nullable=False, server_default="STANDARD"
        ),
        sa.Column("source_document", sa.String(100), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="KWD"),
        sa.Column(
            "exchange_rate",
            sa.Numeric(18, 6),
            nullable=False,
            server_default="1",
        ),
        sa.Column("idempotency_key", sa.String(100), nullable=True),
        sa.Column(
            "status", sa.String(10), nullable=False, server_default="DRAFT"
        ),
        sa.Column("reversed_entry_id", sa.BigInteger, nullable=True),
        sa.Column(
            "posting_template_id",
            sa.BigInteger,
            sa.ForeignKey("posting_template_headers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        *_ts(),
        *_audit(),
    )
    op.create_foreign_key(
        "fk_journal_entries_reversed",
        "journal_entries",
        "journal_entries",
        ["reversed_entry_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "uq_journal_entries_company_number",
        "journal_entries",
        ["company_id", "entry_number"],
        unique=True,
    )
    op.create_index(
        "uq_journal_entries_idempotency",
        "journal_entries",
        ["idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.create_index(
        "ix_journal_entries_company_date",
        "journal_entries",
        ["company_id", "entry_date"],
    )
    op.create_index(
        "ix_journal_entries_period",
        "journal_entries",
        ["period_id"],
    )

    # ------------------------------------------------------------------
    # 11. journal_entry_lines
    # ------------------------------------------------------------------
    op.create_table(
        "journal_entry_lines",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "entry_id",
            sa.BigInteger,
            sa.ForeignKey("journal_entries.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.BigInteger,
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "debit",
            sa.Numeric(18, 3),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "credit",
            sa.Numeric(18, 3),
            nullable=False,
            server_default="0",
        ),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "cost_center_id",
            sa.BigInteger,
            sa.ForeignKey("cost_centers.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "branch_id",
            sa.BigInteger,
            sa.ForeignKey("branches.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("sequence", sa.Integer, nullable=False, server_default="0"),
        *_ts(),
        sa.CheckConstraint(
            "(debit > 0 AND credit = 0) OR (debit = 0 AND credit > 0)",
            name="ck_jel_exactly_one_side",
        ),
    )
    op.create_index("ix_jel_entry_id", "journal_entry_lines", ["entry_id"])
    op.create_index("ix_jel_account_id", "journal_entry_lines", ["account_id"])


def downgrade() -> None:
    op.drop_table("journal_entry_lines")
    op.drop_table("journal_entries")
    op.drop_table("posting_template_lines")
    op.drop_table("posting_template_headers")
    op.drop_table("accounting_periods")
    op.drop_table("fiscal_years")
    op.drop_table("accounts")
    op.drop_table("coa_template_lines")
    op.drop_table("coa_templates")
    op.drop_table("cost_centers")
    op.drop_table("accounting_settings")
