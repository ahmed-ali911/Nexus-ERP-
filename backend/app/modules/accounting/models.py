from __future__ import annotations

import datetime
import decimal
import enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.mixins import AuditMixin, SoftDeleteMixin, TimestampMixin
from app.modules.organization.mixins import CompanyScopedMixin


class AccountType(enum.StrEnum):
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    REVENUE = "REVENUE"
    EXPENSE = "EXPENSE"


class SourceModule(enum.StrEnum):
    MANUAL = "MANUAL"
    SALES = "SALES"
    PURCHASING = "PURCHASING"
    INVENTORY = "INVENTORY"
    SYSTEM = "SYSTEM"


class EntryType(enum.StrEnum):
    STANDARD = "STANDARD"
    OPENING = "OPENING"
    CLOSING = "CLOSING"
    ADJUSTMENT = "ADJUSTMENT"


class JournalEntryStatus(enum.StrEnum):
    DRAFT = "DRAFT"
    POSTED = "POSTED"
    REVERSED = "REVERSED"


class FiscalYearStatus(enum.StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class PeriodStatus(enum.StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    REOPENED = "REOPENED"


class AccountSelectorType(enum.StrEnum):
    """Closed enum — not a free-text DSL. Safety-critical: adding a new
    selector requires a code change and review, not just a data row."""

    FIXED_CODE = "FIXED_CODE"
    PAYLOAD_ACCOUNT_ID = "PAYLOAD_ACCOUNT_ID"
    PAYLOAD_ACCOUNT_CODE = "PAYLOAD_ACCOUNT_CODE"
    CUSTOMER_AR = "CUSTOMER_AR"
    SUPPLIER_AP = "SUPPLIER_AP"
    SALES_REVENUE = "SALES_REVENUE"
    SALES_DISCOUNT = "SALES_DISCOUNT"
    COGS_ACCOUNT = "COGS_ACCOUNT"
    INVENTORY_ASSET = "INVENTORY_ASSET"
    TAX_PAYABLE = "TAX_PAYABLE"
    BANK_CLEARING = "BANK_CLEARING"
    PURCHASE_CLEARING = "PURCHASE_CLEARING"


# ---------------------------------------------------------------------------
# AccountingSettings
# ---------------------------------------------------------------------------


class AccountingSettings(Base, CompanyScopedMixin, TimestampMixin, AuditMixin):
    __tablename__ = "accounting_settings"
    __table_args__ = (Index("uq_accounting_settings_company", "company_id", unique=True),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    je_prefix: Mapped[str] = mapped_column(
        String(10), nullable=False, default="JE", server_default="JE"
    )
    last_je_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    default_currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="KWD", server_default="KWD"
    )
    require_manual_je_approval: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    allow_backdated_entries: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    coa_template_code: Mapped[str | None] = mapped_column(String(50), nullable=True)


# ---------------------------------------------------------------------------
# CostCenter
# ---------------------------------------------------------------------------


class CostCenter(Base, CompanyScopedMixin, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "cost_centers"
    __table_args__ = (
        Index(
            "uq_cost_centers_company_code",
            "company_id",
            "code",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name_en: Mapped[str] = mapped_column(String(200), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("cost_centers.id", ondelete="RESTRICT"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )


# ---------------------------------------------------------------------------
# Account (Chart of Accounts)
# ---------------------------------------------------------------------------


class Account(Base, CompanyScopedMixin, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "accounts"
    __table_args__ = (
        Index(
            "uq_accounts_company_code",
            "company_id",
            "code",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name_en: Mapped[str] = mapped_column(String(200), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    account_type: Mapped[AccountType] = mapped_column(
        SAEnum(
            AccountType,
            native_enum=False,
            validate_strings=True,
            length=12,
            name="ck_accounts_type",
        ),
        nullable=False,
    )
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=True
    )
    is_postable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sequence: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )


# ---------------------------------------------------------------------------
# CoA Templates (system-level; company_id-free)
# ---------------------------------------------------------------------------


class CoATemplate(Base, TimestampMixin):
    __tablename__ = "coa_templates"
    __table_args__ = (UniqueConstraint("code", name="uq_coa_templates_code"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name_en: Mapped[str] = mapped_column(String(200), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class CoATemplateLine(Base, TimestampMixin):
    __tablename__ = "coa_template_lines"
    __table_args__ = (
        Index("ix_coa_tpl_lines_template", "template_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    template_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("coa_templates.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name_en: Mapped[str] = mapped_column(String(200), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    account_type: Mapped[AccountType] = mapped_column(
        SAEnum(
            AccountType,
            native_enum=False,
            validate_strings=True,
            length=12,
            name="ck_coa_tpl_lines_type",
        ),
        nullable=False,
    )
    parent_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_postable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    sequence: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )


# ---------------------------------------------------------------------------
# FiscalYear
# ---------------------------------------------------------------------------


class FiscalYear(Base, CompanyScopedMixin, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "fiscal_years"
    __table_args__ = (
        Index(
            "uq_fiscal_years_company_code",
            "company_id",
            "code",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name_en: Mapped[str] = mapped_column(String(100), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(100), nullable=False)
    start_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    status: Mapped[FiscalYearStatus] = mapped_column(
        SAEnum(
            FiscalYearStatus,
            native_enum=False,
            validate_strings=True,
            length=10,
            name="ck_fiscal_years_status",
        ),
        nullable=False,
        default=FiscalYearStatus.OPEN,
        server_default="OPEN",
    )


# ---------------------------------------------------------------------------
# AccountingPeriod
# ---------------------------------------------------------------------------


class AccountingPeriod(Base, CompanyScopedMixin, TimestampMixin, AuditMixin):
    __tablename__ = "accounting_periods"
    __table_args__ = (
        Index(
            "uq_accounting_periods_company_fy_no",
            "company_id",
            "fiscal_year_id",
            "period_no",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    fiscal_year_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("fiscal_years.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    period_no: Mapped[int] = mapped_column(Integer, nullable=False)
    name_en: Mapped[str] = mapped_column(String(100), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(100), nullable=False)
    start_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    status: Mapped[PeriodStatus] = mapped_column(
        SAEnum(
            PeriodStatus,
            native_enum=False,
            validate_strings=True,
            length=10,
            name="ck_accounting_periods_status",
        ),
        nullable=False,
        default=PeriodStatus.OPEN,
        server_default="OPEN",
    )


# ---------------------------------------------------------------------------
# PostingTemplateHeader  (company_id=NULL → global/system template)
# ---------------------------------------------------------------------------


class PostingTemplateHeader(Base, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "posting_template_headers"
    __table_args__ = (
        Index(
            "uq_posting_tmpl_company_event_ver",
            "company_id",
            "event_type",
            "version",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # NULL = global/system template; set = company-specific override
    company_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("companies.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    effective_from: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


# ---------------------------------------------------------------------------
# PostingTemplateLine
# ---------------------------------------------------------------------------


class PostingTemplateLine(Base, TimestampMixin):
    __tablename__ = "posting_template_lines"
    __table_args__ = (Index("ix_posting_tmpl_lines_header", "header_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    header_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("posting_template_headers.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    selector_type: Mapped[AccountSelectorType] = mapped_column(
        SAEnum(
            AccountSelectorType,
            native_enum=False,
            validate_strings=True,
            length=25,
            name="ck_posting_tmpl_lines_selector",
        ),
        nullable=False,
    )
    # For FIXED_CODE: account code literal.
    # For PAYLOAD_*: payload field name containing the id/code.
    # For semantic selectors (CUSTOMER_AR, etc.): context key to resolve.
    selector_param: Mapped[str] = mapped_column(String(60), nullable=False)
    side: Mapped[str] = mapped_column(String(6), nullable=False)  # DEBIT | CREDIT
    # Dot-path into the payload dict, e.g. "total_amount" or "lines[0].amount"
    amount_source: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


# ---------------------------------------------------------------------------
# JournalEntry  (NO SoftDeleteMixin — immutable; corrections via reversals)
# ---------------------------------------------------------------------------


class JournalEntry(Base, CompanyScopedMixin, TimestampMixin, AuditMixin):
    __tablename__ = "journal_entries"
    __table_args__ = (
        # Partial unique on idempotency_key (only rows where it is set)
        Index(
            "uq_journal_entries_idempotency",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        Index("uq_journal_entries_company_number", "company_id", "entry_number", unique=True),
        Index("ix_journal_entries_company_date", "company_id", "entry_date"),
        Index("ix_journal_entries_period", "period_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    entry_number: Mapped[str] = mapped_column(String(30), nullable=False)
    entry_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    period_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("accounting_periods.id", ondelete="RESTRICT"),
        nullable=True,
    )
    source_module: Mapped[SourceModule] = mapped_column(
        SAEnum(
            SourceModule,
            native_enum=False,
            validate_strings=True,
            length=15,
            name="ck_journal_entries_source",
        ),
        nullable=False,
        default=SourceModule.MANUAL,
        server_default="MANUAL",
    )
    entry_type: Mapped[EntryType] = mapped_column(
        SAEnum(
            EntryType,
            native_enum=False,
            validate_strings=True,
            length=12,
            name="ck_journal_entries_entry_type",
        ),
        nullable=False,
        default=EntryType.STANDARD,
        server_default="STANDARD",
    )
    # Human-readable reference, e.g. "INV-2026-001" for traceable auto-posts
    source_document: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="KWD", server_default="KWD"
    )
    exchange_rate: Mapped[decimal.Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=decimal.Decimal("1"), server_default="1"
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[JournalEntryStatus] = mapped_column(
        SAEnum(
            JournalEntryStatus,
            native_enum=False,
            validate_strings=True,
            length=10,
            name="ck_journal_entries_status",
        ),
        nullable=False,
        default=JournalEntryStatus.DRAFT,
        server_default="DRAFT",
    )
    reversed_entry_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("journal_entries.id", ondelete="RESTRICT"),
        nullable=True,
    )
    posting_template_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("posting_template_headers.id", ondelete="SET NULL"),
        nullable=True,
    )


# ---------------------------------------------------------------------------
# JournalEntryLine
# ---------------------------------------------------------------------------


class JournalEntryLine(Base, TimestampMixin):
    __tablename__ = "journal_entry_lines"
    __table_args__ = (
        # Exactly one side must be positive; the other must be zero.
        CheckConstraint(
            "(debit > 0 AND credit = 0) OR (debit = 0 AND credit > 0)",
            name="ck_jel_exactly_one_side",
        ),
        Index("ix_jel_entry_id", "entry_id"),
        Index("ix_jel_account_id", "account_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    entry_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("journal_entries.id", ondelete="RESTRICT"),
        nullable=False,
    )
    account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    debit: Mapped[decimal.Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
        default=decimal.Decimal("0"),
        server_default="0",
    )
    credit: Mapped[decimal.Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
        default=decimal.Decimal("0"),
        server_default="0",
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_center_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("cost_centers.id", ondelete="RESTRICT"),
        nullable=True,
    )
    branch_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("branches.id", ondelete="RESTRICT"),
        nullable=True,
    )
    sequence: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
