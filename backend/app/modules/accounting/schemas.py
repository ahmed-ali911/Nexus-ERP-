from __future__ import annotations

import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import (
    AccountSelectorType,
    AccountType,
    EntryType,
    FiscalYearStatus,
    JournalEntryStatus,
    PeriodStatus,
    SourceModule,
)


# ---------------------------------------------------------------------------
# AccountingSettings
# ---------------------------------------------------------------------------


class AccountingSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    je_prefix: str
    last_je_number: int
    default_currency: str
    require_manual_je_approval: bool
    allow_backdated_entries: bool
    coa_template_code: str | None
    enable_auto_posting: bool
    default_ar_account_code: str | None
    default_cash_account_code: str | None
    default_sales_revenue_account_code: str | None
    default_tax_payable_account_code: str | None
    default_inventory_account_code: str | None
    default_cogs_account_code: str | None
    default_ap_account_code: str | None
    default_grn_accrual_account_code: str | None
    default_inventory_adjustment_account_code: str | None
    default_purchase_variance_account_code: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class AccountingSettingsUpdate(BaseModel):
    je_prefix: str | None = Field(default=None, max_length=10)
    default_currency: str | None = Field(default=None, max_length=3)
    require_manual_je_approval: bool | None = None
    allow_backdated_entries: bool | None = None
    enable_auto_posting: bool | None = None
    default_ar_account_code: str | None = Field(default=None, max_length=20)
    default_cash_account_code: str | None = Field(default=None, max_length=20)
    default_sales_revenue_account_code: str | None = Field(default=None, max_length=20)
    default_tax_payable_account_code: str | None = Field(default=None, max_length=20)
    default_inventory_account_code: str | None = Field(default=None, max_length=20)
    default_cogs_account_code: str | None = Field(default=None, max_length=20)
    default_ap_account_code: str | None = Field(default=None, max_length=20)
    default_grn_accrual_account_code: str | None = Field(default=None, max_length=20)
    default_inventory_adjustment_account_code: str | None = Field(default=None, max_length=20)
    default_purchase_variance_account_code: str | None = Field(default=None, max_length=20)


# ---------------------------------------------------------------------------
# CostCenter
# ---------------------------------------------------------------------------


class CostCenterCreate(BaseModel):
    code: str = Field(max_length=20)
    name_en: str = Field(max_length=200)
    name_ar: str = Field(max_length=200)
    parent_id: int | None = None
    is_active: bool = True


class CostCenterUpdate(BaseModel):
    name_en: str | None = Field(default=None, max_length=200)
    name_ar: str | None = Field(default=None, max_length=200)
    parent_id: int | None = None
    is_active: bool | None = None


class CostCenterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    code: str
    name_en: str
    name_ar: str
    parent_id: int | None
    is_active: bool
    is_deleted: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime
    created_by: int | None
    updated_by: int | None


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------


class AccountCreate(BaseModel):
    code: str = Field(max_length=20)
    name_en: str = Field(max_length=200)
    name_ar: str = Field(max_length=200)
    account_type: AccountType
    parent_id: int | None = None
    is_postable: bool = True
    description: str | None = None
    sequence: int = 0


class AccountUpdate(BaseModel):
    name_en: str | None = Field(default=None, max_length=200)
    name_ar: str | None = Field(default=None, max_length=200)
    parent_id: int | None = None
    is_postable: bool | None = None
    description: str | None = None
    sequence: int | None = None


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    code: str
    name_en: str
    name_ar: str
    account_type: AccountType
    parent_id: int | None
    is_postable: bool
    description: str | None
    sequence: int
    is_deleted: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime
    created_by: int | None
    updated_by: int | None


# ---------------------------------------------------------------------------
# CoATemplate
# ---------------------------------------------------------------------------


class CoATemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name_en: str
    name_ar: str
    description: str | None


class ApplyTemplateRequest(BaseModel):
    template_code: str


# ---------------------------------------------------------------------------
# FiscalYear
# ---------------------------------------------------------------------------


class FiscalYearCreate(BaseModel):
    code: str = Field(max_length=20)
    name_en: str = Field(max_length=100)
    name_ar: str = Field(max_length=100)
    start_date: datetime.date
    end_date: datetime.date

    @model_validator(mode="after")
    def _end_after_start(self) -> FiscalYearCreate:
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class FiscalYearResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    code: str
    name_en: str
    name_ar: str
    start_date: datetime.date
    end_date: datetime.date
    status: FiscalYearStatus
    is_deleted: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ---------------------------------------------------------------------------
# AccountingPeriod
# ---------------------------------------------------------------------------


class GeneratePeriodsRequest(BaseModel):
    fiscal_year_id: int
    count: int = Field(ge=1, le=52, description="Number of periods to generate (e.g. 12 for monthly)")


class AccountingPeriodResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    fiscal_year_id: int
    period_no: int
    name_en: str
    name_ar: str
    start_date: datetime.date
    end_date: datetime.date
    status: PeriodStatus
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ---------------------------------------------------------------------------
# PostingTemplate
# ---------------------------------------------------------------------------


class PostingTemplateLineCreate(BaseModel):
    sequence: int = 0
    selector_type: AccountSelectorType
    selector_param: str = Field(max_length=60)
    side: str = Field(pattern=r"^(DEBIT|CREDIT)$")
    amount_source: str = Field(max_length=100)
    description: str | None = None


class PostingTemplateCreate(BaseModel):
    event_type: str = Field(max_length=60)
    version: int = 1
    effective_from: datetime.date
    effective_to: datetime.date | None = None
    description: str | None = None
    lines: list[PostingTemplateLineCreate] = Field(min_length=2)


class PostingTemplateLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    header_id: int
    sequence: int
    selector_type: AccountSelectorType
    selector_param: str
    side: str
    amount_source: str
    description: str | None


class PostingTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int | None
    event_type: str
    version: int
    effective_from: datetime.date
    effective_to: datetime.date | None
    description: str | None
    is_deleted: bool
    lines: list[PostingTemplateLineResponse] = []


# ---------------------------------------------------------------------------
# JournalEntry
# ---------------------------------------------------------------------------


class JournalEntryLineCreate(BaseModel):
    account_id: int
    debit: Decimal = Field(default=Decimal("0"), ge=0)
    credit: Decimal = Field(default=Decimal("0"), ge=0)
    description: str | None = None
    cost_center_id: int | None = None
    branch_id: int | None = None
    sequence: int = 0

    @model_validator(mode="after")
    def _exactly_one_side(self) -> JournalEntryLineCreate:
        if self.debit > 0 and self.credit > 0:
            raise ValueError("A journal entry line cannot have both debit and credit > 0")
        if self.debit == 0 and self.credit == 0:
            raise ValueError("A journal entry line must have debit > 0 or credit > 0")
        return self


class JournalEntryCreate(BaseModel):
    entry_date: datetime.date
    description: str | None = None
    entry_type: EntryType = EntryType.STANDARD
    source_document: str | None = Field(default=None, max_length=100)
    currency: str = Field(default="KWD", max_length=3)
    idempotency_key: str | None = Field(default=None, max_length=100)
    lines: list[JournalEntryLineCreate] = Field(min_length=2)


class JournalEntryLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entry_id: int
    account_id: int
    debit: Decimal
    credit: Decimal
    description: str | None
    cost_center_id: int | None
    branch_id: int | None
    sequence: int


class JournalEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    entry_number: str
    entry_date: datetime.date
    period_id: int | None
    source_module: SourceModule
    entry_type: EntryType
    source_document: str | None
    description: str | None
    currency: str
    exchange_rate: Decimal
    idempotency_key: str | None
    status: JournalEntryStatus
    reversed_entry_id: int | None
    posting_template_id: int | None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    created_by: int | None
    lines: list[JournalEntryLineResponse] = []


class ReverseEntryRequest(BaseModel):
    reversal_date: datetime.date
    description: str | None = None


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


class TrialBalanceLine(BaseModel):
    account_id: int
    account_code: str
    account_name: str
    account_type: AccountType
    total_debit: Decimal
    total_credit: Decimal
    balance: Decimal  # debit - credit (positive = debit-normal balance)


class TrialBalanceReport(BaseModel):
    as_of_date: datetime.date
    lines: list[TrialBalanceLine]
    grand_total_debit: Decimal
    grand_total_credit: Decimal
    is_balanced: bool


class PLLine(BaseModel):
    account_id: int
    account_code: str
    account_name: str
    account_type: AccountType
    net_amount: Decimal  # positive = revenue net / expense net


class PLReport(BaseModel):
    from_date: datetime.date
    to_date: datetime.date
    revenue_lines: list[PLLine]
    expense_lines: list[PLLine]
    total_revenue: Decimal
    total_expenses: Decimal
    net_income: Decimal


class BalanceSheetLine(BaseModel):
    account_id: int
    account_code: str
    account_name: str
    balance: Decimal


class BalanceSheetReport(BaseModel):
    as_of_date: datetime.date
    assets: list[BalanceSheetLine]
    liabilities: list[BalanceSheetLine]
    equity: list[BalanceSheetLine]
    retained_earnings: Decimal  # computed net income since inception
    total_assets: Decimal
    total_liabilities: Decimal
    total_equity_paid_in: Decimal
    total_equity: Decimal  # paid-in + retained earnings
    is_balanced: bool


class GLEntry(BaseModel):
    entry_id: int
    entry_number: str
    entry_date: datetime.date
    source_document: str | None
    description: str | None
    line_description: str | None
    debit: Decimal
    credit: Decimal
    running_balance: Decimal


class GLReport(BaseModel):
    account_id: int
    account_code: str
    account_name: str
    account_type: AccountType
    from_date: datetime.date
    to_date: datetime.date
    opening_balance: Decimal
    entries: list[GLEntry]
    closing_balance: Decimal
