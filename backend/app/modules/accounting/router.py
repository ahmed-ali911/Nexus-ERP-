from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import require_permission
from app.modules.auth.models import User

from . import schemas, service
from .models import AccountType, JournalEntryStatus

router = APIRouter(prefix="/accounting", tags=["accounting"])


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


@router.get("/settings", response_model=schemas.AccountingSettingsResponse)
def get_settings(
    current_user: User = Depends(require_permission("accounting.settings.view")),
    db: Session = Depends(get_db),
):
    return service.get_or_create_settings(db, current_user.company_id)


@router.patch("/settings", response_model=schemas.AccountingSettingsResponse)
def update_settings(
    payload: schemas.AccountingSettingsUpdate,
    current_user: User = Depends(require_permission("accounting.settings.update")),
    db: Session = Depends(get_db),
):
    return service.update_settings(db, payload, current_user.company_id, current_user.id)


# ---------------------------------------------------------------------------
# Chart of Accounts — templates
# ---------------------------------------------------------------------------


@router.get("/coa-templates", response_model=list[schemas.CoATemplateResponse])
def list_coa_templates(
    current_user: User = Depends(require_permission("accounting.accounts.view")),
    db: Session = Depends(get_db),
):
    return service.list_coa_templates(db)


@router.post("/coa-templates/apply", response_model=list[schemas.AccountResponse])
def apply_coa_template(
    payload: schemas.ApplyTemplateRequest,
    current_user: User = Depends(require_permission("accounting.accounts.manage")),
    db: Session = Depends(get_db),
):
    return service.apply_coa_template(
        db, current_user.company_id, payload.template_code, current_user.id
    )


# ---------------------------------------------------------------------------
# Chart of Accounts — accounts
# ---------------------------------------------------------------------------


@router.post(
    "/accounts",
    response_model=schemas.AccountResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_account(
    payload: schemas.AccountCreate,
    current_user: User = Depends(require_permission("accounting.accounts.manage")),
    db: Session = Depends(get_db),
):
    return service.create_account(db, payload, current_user.company_id, current_user.id)


@router.get("/accounts", response_model=list[schemas.AccountResponse])
def list_accounts(
    account_type: AccountType | None = Query(default=None),
    postable_only: bool = Query(default=False),
    current_user: User = Depends(require_permission("accounting.accounts.view")),
    db: Session = Depends(get_db),
):
    return service.list_accounts(
        db, current_user.company_id, account_type=account_type, postable_only=postable_only
    )


@router.get("/accounts/{account_id}", response_model=schemas.AccountResponse)
def get_account(
    account_id: int,
    current_user: User = Depends(require_permission("accounting.accounts.view")),
    db: Session = Depends(get_db),
):
    return service.get_account(db, account_id, current_user.company_id)


@router.patch("/accounts/{account_id}", response_model=schemas.AccountResponse)
def update_account(
    account_id: int,
    payload: schemas.AccountUpdate,
    current_user: User = Depends(require_permission("accounting.accounts.manage")),
    db: Session = Depends(get_db),
):
    return service.update_account(
        db, account_id, payload, current_user.company_id, current_user.id
    )


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    account_id: int,
    current_user: User = Depends(require_permission("accounting.accounts.manage")),
    db: Session = Depends(get_db),
):
    service.delete_account(db, account_id, current_user.company_id, current_user.id)


# ---------------------------------------------------------------------------
# Cost Centers
# ---------------------------------------------------------------------------


@router.post(
    "/cost-centers",
    response_model=schemas.CostCenterResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_cost_center(
    payload: schemas.CostCenterCreate,
    current_user: User = Depends(require_permission("accounting.cost_centers.manage")),
    db: Session = Depends(get_db),
):
    return service.create_cost_center(db, payload, current_user.company_id, current_user.id)


@router.get("/cost-centers", response_model=list[schemas.CostCenterResponse])
def list_cost_centers(
    current_user: User = Depends(require_permission("accounting.cost_centers.view")),
    db: Session = Depends(get_db),
):
    return service.list_cost_centers(db, current_user.company_id)


# ---------------------------------------------------------------------------
# Fiscal Years
# ---------------------------------------------------------------------------


@router.post(
    "/fiscal-years",
    response_model=schemas.FiscalYearResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_fiscal_year(
    payload: schemas.FiscalYearCreate,
    current_user: User = Depends(require_permission("accounting.fiscal_years.manage")),
    db: Session = Depends(get_db),
):
    return service.create_fiscal_year(db, payload, current_user.company_id, current_user.id)


@router.get("/fiscal-years", response_model=list[schemas.FiscalYearResponse])
def list_fiscal_years(
    current_user: User = Depends(require_permission("accounting.fiscal_years.view")),
    db: Session = Depends(get_db),
):
    return service.list_fiscal_years(db, current_user.company_id)


@router.post("/fiscal-years/{fy_id}/close", response_model=schemas.FiscalYearResponse)
def close_fiscal_year(
    fy_id: int,
    current_user: User = Depends(require_permission("accounting.fiscal_years.manage")),
    db: Session = Depends(get_db),
):
    return service.close_fiscal_year(db, fy_id, current_user.company_id, current_user.id)


# ---------------------------------------------------------------------------
# Accounting Periods
# ---------------------------------------------------------------------------


@router.post(
    "/periods/generate",
    response_model=list[schemas.AccountingPeriodResponse],
    status_code=status.HTTP_201_CREATED,
)
def generate_periods(
    payload: schemas.GeneratePeriodsRequest,
    current_user: User = Depends(require_permission("accounting.periods.manage")),
    db: Session = Depends(get_db),
):
    return service.generate_periods(db, payload, current_user.company_id, current_user.id)


@router.get(
    "/periods",
    response_model=list[schemas.AccountingPeriodResponse],
)
def list_periods(
    fiscal_year_id: int = Query(...),
    current_user: User = Depends(require_permission("accounting.periods.view")),
    db: Session = Depends(get_db),
):
    return service.list_periods(db, current_user.company_id, fiscal_year_id)


@router.post("/periods/{period_id}/close", response_model=schemas.AccountingPeriodResponse)
def close_period(
    period_id: int,
    current_user: User = Depends(require_permission("accounting.periods.manage")),
    db: Session = Depends(get_db),
):
    return service.close_period(db, period_id, current_user.company_id, current_user.id)


@router.post("/periods/{period_id}/reopen", response_model=schemas.AccountingPeriodResponse)
def reopen_period(
    period_id: int,
    reason: str | None = Query(default=None),
    current_user: User = Depends(require_permission("accounting.periods.manage")),
    db: Session = Depends(get_db),
):
    return service.reopen_period(
        db, period_id, current_user.company_id, current_user.id, reason=reason
    )


# ---------------------------------------------------------------------------
# Posting Templates
# ---------------------------------------------------------------------------


@router.post(
    "/posting-templates",
    response_model=schemas.PostingTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_posting_template(
    payload: schemas.PostingTemplateCreate,
    current_user: User = Depends(require_permission("accounting.posting_templates.manage")),
    db: Session = Depends(get_db),
):
    return service.create_posting_template(
        db, payload, company_id=current_user.company_id, actor_id=current_user.id
    )


# ---------------------------------------------------------------------------
# Journal Entries
# ---------------------------------------------------------------------------


@router.post(
    "/journal-entries",
    response_model=schemas.JournalEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_journal_entry(
    payload: schemas.JournalEntryCreate,
    current_user: User = Depends(require_permission("accounting.journal_entries.create")),
    db: Session = Depends(get_db),
):
    return service.create_journal_entry(
        db, payload, current_user.company_id, current_user.id
    )


@router.get("/journal-entries", response_model=list[schemas.JournalEntryResponse])
def list_journal_entries(
    status_filter: JournalEntryStatus | None = Query(default=None, alias="status"),
    from_date: datetime.date | None = Query(default=None),
    to_date: datetime.date | None = Query(default=None),
    current_user: User = Depends(require_permission("accounting.journal_entries.view")),
    db: Session = Depends(get_db),
):
    return service.list_journal_entries(
        db, current_user.company_id,
        status=status_filter, from_date=from_date, to_date=to_date,
    )


@router.get("/journal-entries/{entry_id}", response_model=schemas.JournalEntryResponse)
def get_journal_entry(
    entry_id: int,
    current_user: User = Depends(require_permission("accounting.journal_entries.view")),
    db: Session = Depends(get_db),
):
    return service.get_journal_entry(db, entry_id, current_user.company_id)


@router.post("/journal-entries/{entry_id}/post", response_model=schemas.JournalEntryResponse)
def post_journal_entry(
    entry_id: int,
    current_user: User = Depends(require_permission("accounting.journal_entries.post")),
    db: Session = Depends(get_db),
):
    return service.post_journal_entry(db, entry_id, current_user.company_id, current_user.id)


@router.post(
    "/journal-entries/{entry_id}/reverse",
    response_model=schemas.JournalEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
def reverse_journal_entry(
    entry_id: int,
    payload: schemas.ReverseEntryRequest,
    current_user: User = Depends(require_permission("accounting.journal_entries.reverse")),
    db: Session = Depends(get_db),
):
    return service.reverse_journal_entry(
        db, entry_id, payload.reversal_date, current_user.company_id,
        current_user.id, description=payload.description,
    )


@router.post("/approvals/{approval_id}/decide")
def decide_approval(
    approval_id: int,
    approve: bool = Query(...),
    current_user: User = Depends(require_permission("accounting.approval.decide")),
    db: Session = Depends(get_db),
):
    return service.decide_approval(
        db, approval_id, approve, current_user.company_id, current_user.id
    )


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


@router.get("/reports/trial-balance", response_model=schemas.TrialBalanceReport)
def trial_balance(
    as_of_date: datetime.date = Query(...),
    cost_center_id: int | None = Query(default=None),
    current_user: User = Depends(require_permission("accounting.reports.view")),
    db: Session = Depends(get_db),
):
    return service.get_trial_balance(
        db, current_user.company_id, as_of_date, cost_center_id=cost_center_id
    )


@router.get("/reports/pl", response_model=schemas.PLReport)
def profit_and_loss(
    from_date: datetime.date = Query(...),
    to_date: datetime.date = Query(...),
    cost_center_id: int | None = Query(default=None),
    current_user: User = Depends(require_permission("accounting.reports.view")),
    db: Session = Depends(get_db),
):
    return service.get_pl(
        db, current_user.company_id, from_date, to_date, cost_center_id=cost_center_id
    )


@router.get("/reports/balance-sheet", response_model=schemas.BalanceSheetReport)
def balance_sheet(
    as_of_date: datetime.date = Query(...),
    current_user: User = Depends(require_permission("accounting.reports.view")),
    db: Session = Depends(get_db),
):
    return service.get_balance_sheet(db, current_user.company_id, as_of_date)


@router.get("/reports/gl/{account_id}", response_model=schemas.GLReport)
def general_ledger(
    account_id: int,
    from_date: datetime.date = Query(...),
    to_date: datetime.date = Query(...),
    current_user: User = Depends(require_permission("accounting.reports.view")),
    db: Session = Depends(get_db),
):
    return service.get_gl(db, account_id, current_user.company_id, from_date, to_date)
