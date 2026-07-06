"""Accounting service: CoA management, Posting Engine, manual JE workflow,
financial reports.

Posting Engine is FULLY ISOLATED — it imports nothing from sales, purchasing,
or inventory modules.  The PostingService.post() interface is synchronous now
but structured so the caller site can be swapped for an async broker later
without touching this file.
"""
from __future__ import annotations

import calendar
import datetime
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import ApprovalRequired, BusinessRuleViolation, NotFoundError
from app.modules.shared.models import ApprovalRequest, ApprovalRequestType, ApprovalStatus

from . import schemas
from .models import (
    Account,
    AccountType,
    AccountingPeriod,
    AccountingSettings,
    AccountSelectorType,
    CoATemplate,
    CoATemplateLine,
    CostCenter,
    EntryType,
    FiscalYear,
    FiscalYearStatus,
    JournalEntry,
    JournalEntryLine,
    JournalEntryStatus,
    PeriodStatus,
    PostingTemplateHeader,
    PostingTemplateLine,
    SourceModule,
)


# ===========================================================================
# AccountingSettings
# ===========================================================================


def get_or_create_settings(db: Session, company_id: int) -> AccountingSettings:
    s = db.query(AccountingSettings).filter_by(company_id=company_id).first()
    if s is None:
        s = AccountingSettings(company_id=company_id)
        db.add(s)
        db.flush()
    return s


def update_settings(
    db: Session,
    payload: schemas.AccountingSettingsUpdate,
    company_id: int,
    actor_id: int | None,
) -> AccountingSettings:
    s = get_or_create_settings(db, company_id)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(s, k, v)
    s.updated_by = actor_id
    db.flush()
    return s


# ===========================================================================
# CostCenter
# ===========================================================================


def create_cost_center(
    db: Session,
    payload: schemas.CostCenterCreate,
    company_id: int,
    actor_id: int | None,
) -> CostCenter:
    if payload.parent_id is not None:
        parent = (
            db.query(CostCenter)
            .filter_by(id=payload.parent_id, company_id=company_id, is_deleted=False)
            .first()
        )
        if parent is None:
            raise NotFoundError("Parent cost center not found")
        _assert_no_cc_cycle(db, company_id, payload.parent_id, payload.code)

    cc = CostCenter(
        company_id=company_id,
        code=payload.code,
        name_en=payload.name_en,
        name_ar=payload.name_ar,
        parent_id=payload.parent_id,
        is_active=payload.is_active,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(cc)
    db.flush()
    return cc


def _assert_no_cc_cycle(
    db: Session, company_id: int, parent_id: int, new_child_code: str
) -> None:
    visited: set[int] = set()
    cur_id: int | None = parent_id
    while cur_id is not None:
        if cur_id in visited:
            raise BusinessRuleViolation("Cost center hierarchy would create a cycle")
        visited.add(cur_id)
        row = (
            db.query(CostCenter.parent_id, CostCenter.code)
            .filter_by(id=cur_id, company_id=company_id, is_deleted=False)
            .first()
        )
        if row is None:
            break
        if row.code == new_child_code:
            raise BusinessRuleViolation("Cost center hierarchy would create a cycle")
        cur_id = row.parent_id


def list_cost_centers(db: Session, company_id: int) -> list[CostCenter]:
    return (
        db.query(CostCenter)
        .filter_by(company_id=company_id, is_deleted=False)
        .order_by(CostCenter.code)
        .all()
    )


# ===========================================================================
# Chart of Accounts
# ===========================================================================


def apply_coa_template(
    db: Session,
    company_id: int,
    template_code: str,
    actor_id: int | None,
) -> list[Account]:
    tmpl = db.query(CoATemplate).filter_by(code=template_code).first()
    if tmpl is None:
        raise NotFoundError(f"CoA template '{template_code}' not found")

    existing = (
        db.query(Account).filter_by(company_id=company_id, is_deleted=False).first()
    )
    if existing is not None:
        raise BusinessRuleViolation(
            "Chart of accounts already exists for this company."
        )

    lines = (
        db.query(CoATemplateLine)
        .filter_by(template_id=tmpl.id)
        .order_by(CoATemplateLine.sequence)
        .all()
    )

    code_to_id: dict[str, int] = {}
    created: list[Account] = []

    for line in lines:
        parent_id = code_to_id.get(line.parent_code) if line.parent_code else None
        acct = Account(
            company_id=company_id,
            code=line.code,
            name_en=line.name_en,
            name_ar=line.name_ar,
            account_type=line.account_type,
            parent_id=parent_id,
            is_postable=line.is_postable,
            sequence=line.sequence,
            created_by=actor_id,
            updated_by=actor_id,
        )
        db.add(acct)
        db.flush()
        code_to_id[line.code] = acct.id
        created.append(acct)

    settings = get_or_create_settings(db, company_id)
    settings.coa_template_code = template_code
    settings.updated_by = actor_id
    db.flush()
    return created


def create_account(
    db: Session,
    payload: schemas.AccountCreate,
    company_id: int,
    actor_id: int | None,
) -> Account:
    if payload.parent_id is not None:
        parent = (
            db.query(Account)
            .filter_by(id=payload.parent_id, company_id=company_id, is_deleted=False)
            .first()
        )
        if parent is None:
            raise NotFoundError("Parent account not found")
        _assert_no_account_cycle(db, company_id, payload.parent_id, payload.code)

    acct = Account(
        company_id=company_id,
        code=payload.code,
        name_en=payload.name_en,
        name_ar=payload.name_ar,
        account_type=payload.account_type,
        parent_id=payload.parent_id,
        is_postable=payload.is_postable,
        description=payload.description,
        sequence=payload.sequence,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(acct)
    db.flush()
    return acct


def _assert_no_account_cycle(
    db: Session, company_id: int, parent_id: int, new_child_code: str
) -> None:
    visited: set[int] = set()
    cur_id: int | None = parent_id
    while cur_id is not None:
        if cur_id in visited:
            raise BusinessRuleViolation("Account hierarchy would create a cycle")
        visited.add(cur_id)
        row = (
            db.query(Account.parent_id, Account.code)
            .filter_by(id=cur_id, company_id=company_id, is_deleted=False)
            .first()
        )
        if row is None:
            break
        if row.code == new_child_code:
            raise BusinessRuleViolation("Account hierarchy would create a cycle")
        cur_id = row.parent_id


def update_account(
    db: Session,
    account_id: int,
    payload: schemas.AccountUpdate,
    company_id: int,
    actor_id: int | None,
) -> Account:
    acct = _get_account_or_404(db, account_id, company_id)
    data = payload.model_dump(exclude_unset=True)
    if "parent_id" in data and data["parent_id"] is not None:
        _assert_no_account_cycle(db, company_id, data["parent_id"], acct.code)
    for k, v in data.items():
        setattr(acct, k, v)
    acct.updated_by = actor_id
    db.flush()
    return acct


def delete_account(
    db: Session, account_id: int, company_id: int, actor_id: int | None
) -> None:
    acct = _get_account_or_404(db, account_id, company_id)
    if db.query(JournalEntryLine).filter_by(account_id=account_id).first():
        raise BusinessRuleViolation(
            "Cannot delete account that has been used in journal entries"
        )
    if (
        db.query(Account)
        .filter_by(parent_id=account_id, is_deleted=False)
        .first()
    ):
        raise BusinessRuleViolation("Cannot delete account with active child accounts")
    acct.is_deleted = True
    acct.deleted_at = datetime.datetime.now(datetime.timezone.utc)
    acct.updated_by = actor_id
    db.flush()


def list_accounts(
    db: Session,
    company_id: int,
    account_type: AccountType | None = None,
    postable_only: bool = False,
) -> list[Account]:
    q = db.query(Account).filter_by(company_id=company_id, is_deleted=False)
    if account_type is not None:
        q = q.filter(Account.account_type == account_type)
    if postable_only:
        q = q.filter(Account.is_postable == True)  # noqa: E712
    return q.order_by(Account.code).all()


def get_account(db: Session, account_id: int, company_id: int) -> Account:
    return _get_account_or_404(db, account_id, company_id)


def _get_account_or_404(db: Session, account_id: int, company_id: int) -> Account:
    a = db.query(Account).filter_by(
        id=account_id, company_id=company_id, is_deleted=False
    ).first()
    if a is None:
        raise NotFoundError(f"Account {account_id} not found")
    return a


def _get_account_by_code(db: Session, code: str, company_id: int) -> Account:
    a = db.query(Account).filter_by(
        code=code, company_id=company_id, is_deleted=False
    ).first()
    if a is None:
        raise NotFoundError(f"Account code '{code}' not found")
    return a


# ===========================================================================
# CoA Templates
# ===========================================================================


def list_coa_templates(db: Session) -> list[CoATemplate]:
    return db.query(CoATemplate).order_by(CoATemplate.code).all()


# ===========================================================================
# FiscalYear
# ===========================================================================


def create_fiscal_year(
    db: Session,
    payload: schemas.FiscalYearCreate,
    company_id: int,
    actor_id: int | None,
) -> FiscalYear:
    fy = FiscalYear(
        company_id=company_id,
        code=payload.code,
        name_en=payload.name_en,
        name_ar=payload.name_ar,
        start_date=payload.start_date,
        end_date=payload.end_date,
        status=FiscalYearStatus.OPEN,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(fy)
    db.flush()
    return fy


def close_fiscal_year(
    db: Session, fy_id: int, company_id: int, actor_id: int | None
) -> FiscalYear:
    fy = _get_fy_or_404(db, fy_id, company_id)
    if fy.status == FiscalYearStatus.CLOSED:
        raise BusinessRuleViolation("Fiscal year is already closed")
    open_count = (
        db.query(AccountingPeriod)
        .filter_by(fiscal_year_id=fy_id, company_id=company_id)
        .filter(AccountingPeriod.status != PeriodStatus.CLOSED)
        .count()
    )
    if open_count > 0:
        raise BusinessRuleViolation(
            "Cannot close fiscal year while accounting periods remain open"
        )
    fy.status = FiscalYearStatus.CLOSED
    fy.updated_by = actor_id
    db.flush()
    return fy


def list_fiscal_years(db: Session, company_id: int) -> list[FiscalYear]:
    return (
        db.query(FiscalYear)
        .filter_by(company_id=company_id, is_deleted=False)
        .order_by(FiscalYear.start_date)
        .all()
    )


def _get_fy_or_404(db: Session, fy_id: int, company_id: int) -> FiscalYear:
    fy = db.query(FiscalYear).filter_by(
        id=fy_id, company_id=company_id, is_deleted=False
    ).first()
    if fy is None:
        raise NotFoundError(f"Fiscal year {fy_id} not found")
    return fy


# ===========================================================================
# AccountingPeriod
# ===========================================================================


def generate_periods(
    db: Session,
    payload: schemas.GeneratePeriodsRequest,
    company_id: int,
    actor_id: int | None,
) -> list[AccountingPeriod]:
    fy = _get_fy_or_404(db, payload.fiscal_year_id, company_id)
    if (
        db.query(AccountingPeriod)
        .filter_by(fiscal_year_id=fy.id, company_id=company_id)
        .count()
        > 0
    ):
        raise BusinessRuleViolation(
            "Periods already exist for this fiscal year."
        )

    slices = _split_into_periods(fy.start_date, fy.end_date, payload.count)
    month_en = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]
    month_ar = [
        "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
        "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
    ]
    created: list[AccountingPeriod] = []
    for i, (s, e) in enumerate(slices, start=1):
        if payload.count == 12:
            name_en = f"{month_en[s.month - 1]} {s.year}"
            name_ar = f"{month_ar[s.month - 1]} {s.year}"
        else:
            name_en = f"Period {i}"
            name_ar = f"الفترة {i}"
        p = AccountingPeriod(
            company_id=company_id,
            fiscal_year_id=fy.id,
            period_no=i,
            name_en=name_en,
            name_ar=name_ar,
            start_date=s,
            end_date=e,
            status=PeriodStatus.OPEN,
            created_by=actor_id,
            updated_by=actor_id,
        )
        db.add(p)
        db.flush()
        created.append(p)
    return created


def _split_into_periods(
    start: datetime.date, end: datetime.date, count: int
) -> list[tuple[datetime.date, datetime.date]]:
    if count == 12:
        result = []
        cur = start
        for _ in range(12):
            yr, mo = cur.year, cur.month
            last = calendar.monthrange(yr, mo)[1]
            p_end = min(datetime.date(yr, mo, last), end)
            result.append((cur, p_end))
            if mo == 12:
                cur = datetime.date(yr + 1, 1, 1)
            else:
                cur = datetime.date(yr, mo + 1, 1)
            if cur > end:
                break
        if result:
            result[-1] = (result[-1][0], end)
        return result

    total = (end - start).days + 1
    days_each = total // count
    result = []
    cur = start
    for i in range(count):
        p_end = end if i == count - 1 else cur + datetime.timedelta(days=days_each - 1)
        result.append((cur, p_end))
        cur = p_end + datetime.timedelta(days=1)
    return result


def close_period(
    db: Session, period_id: int, company_id: int, actor_id: int | None
) -> AccountingPeriod:
    p = _get_period_or_404(db, period_id, company_id)
    if p.status == PeriodStatus.CLOSED:
        raise BusinessRuleViolation("Period is already closed")
    p.status = PeriodStatus.CLOSED
    p.updated_by = actor_id
    db.flush()
    return p


def reopen_period(
    db: Session,
    period_id: int,
    company_id: int,
    actor_id: int | None,
    reason: str | None = None,
) -> AccountingPeriod:
    p = _get_period_or_404(db, period_id, company_id)
    if p.status != PeriodStatus.CLOSED:
        raise BusinessRuleViolation("Only CLOSED periods can be reopened")

    # Check for existing approved request for this actor
    approved = (
        db.query(ApprovalRequest)
        .filter_by(
            company_id=company_id,
            reference_type="accounting_period",
            reference_id=period_id,
            request_type=ApprovalRequestType.REOPEN_ACCOUNTING_PERIOD,
            status=ApprovalStatus.APPROVED,
        )
        .first()
    )
    if approved:
        p.status = PeriodStatus.REOPENED
        p.updated_by = actor_id
        db.flush()
        return p

    pending = (
        db.query(ApprovalRequest)
        .filter_by(
            company_id=company_id,
            reference_type="accounting_period",
            reference_id=period_id,
            request_type=ApprovalRequestType.REOPEN_ACCOUNTING_PERIOD,
            status=ApprovalStatus.PENDING,
        )
        .first()
    )
    if pending:
        raise ApprovalRequired(
            approval_request_id=pending.id,
            detail="Period reopen is already pending approval",
        )

    req = ApprovalRequest(
        company_id=company_id,
        request_type=ApprovalRequestType.REOPEN_ACCOUNTING_PERIOD,
        reference_type="accounting_period",
        reference_id=period_id,
        requested_by=actor_id,
        reason=reason,
        status=ApprovalStatus.PENDING,
    )
    db.add(req)
    db.flush()
    raise ApprovalRequired(
        approval_request_id=req.id,
        detail="Period reopen requires approval",
    )


def list_periods(
    db: Session, company_id: int, fiscal_year_id: int
) -> list[AccountingPeriod]:
    return (
        db.query(AccountingPeriod)
        .filter_by(company_id=company_id, fiscal_year_id=fiscal_year_id)
        .order_by(AccountingPeriod.period_no)
        .all()
    )


def _get_period_or_404(db: Session, period_id: int, company_id: int) -> AccountingPeriod:
    p = db.query(AccountingPeriod).filter_by(id=period_id, company_id=company_id).first()
    if p is None:
        raise NotFoundError(f"Accounting period {period_id} not found")
    return p


def _resolve_period(
    db: Session, company_id: int, entry_date: datetime.date
) -> AccountingPeriod | None:
    return (
        db.query(AccountingPeriod)
        .filter(
            AccountingPeriod.company_id == company_id,
            AccountingPeriod.start_date <= entry_date,
            AccountingPeriod.end_date >= entry_date,
            AccountingPeriod.status.in_([PeriodStatus.OPEN, PeriodStatus.REOPENED]),
        )
        .first()
    )


# ===========================================================================
# Posting Templates
# ===========================================================================


def create_posting_template(
    db: Session,
    payload: schemas.PostingTemplateCreate,
    company_id: int | None,
    actor_id: int | None,
) -> PostingTemplateHeader:
    hdr = PostingTemplateHeader(
        company_id=company_id,
        event_type=payload.event_type,
        version=payload.version,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        description=payload.description,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(hdr)
    db.flush()
    for ln in payload.lines:
        db.add(PostingTemplateLine(
            header_id=hdr.id,
            sequence=ln.sequence,
            selector_type=ln.selector_type,
            selector_param=ln.selector_param,
            side=ln.side,
            amount_source=ln.amount_source,
            description=ln.description,
        ))
    db.flush()
    return hdr


def _resolve_template(
    db: Session,
    company_id: int,
    event_type: str,
    entry_date: datetime.date,
) -> PostingTemplateHeader | None:
    """Company-specific override beats global; highest version wins."""
    effective_filter = or_(
        PostingTemplateHeader.effective_to == None,  # noqa: E711
        PostingTemplateHeader.effective_to >= entry_date,
    )

    # Company-specific first
    hdr = (
        db.query(PostingTemplateHeader)
        .filter(
            PostingTemplateHeader.company_id == company_id,
            PostingTemplateHeader.event_type == event_type,
            PostingTemplateHeader.effective_from <= entry_date,
            PostingTemplateHeader.is_deleted == False,  # noqa: E712
            effective_filter,
        )
        .order_by(PostingTemplateHeader.version.desc())
        .first()
    )
    if hdr:
        return hdr

    # Global fallback (company_id IS NULL)
    return (
        db.query(PostingTemplateHeader)
        .filter(
            PostingTemplateHeader.company_id == None,  # noqa: E711
            PostingTemplateHeader.event_type == event_type,
            PostingTemplateHeader.effective_from <= entry_date,
            PostingTemplateHeader.is_deleted == False,  # noqa: E712
            effective_filter,
        )
        .order_by(PostingTemplateHeader.version.desc())
        .first()
    )


# ===========================================================================
# Journal Entry — manual workflow
# ===========================================================================


def create_journal_entry(
    db: Session,
    payload: schemas.JournalEntryCreate,
    company_id: int,
    actor_id: int | None,
) -> JournalEntry:
    # Idempotency short-circuit
    if payload.idempotency_key:
        existing = (
            db.query(JournalEntry)
            .filter_by(idempotency_key=payload.idempotency_key)
            .first()
        )
        if existing is not None:
            if existing.company_id != company_id:
                raise NotFoundError("Journal entry not found")
            return existing

    settings = get_or_create_settings(db, company_id)
    entry_number = _next_je_number(db, settings)

    je = JournalEntry(
        company_id=company_id,
        entry_number=entry_number,
        entry_date=payload.entry_date,
        source_module=SourceModule.MANUAL,
        entry_type=payload.entry_type,
        source_document=payload.source_document,
        description=payload.description,
        currency=payload.currency,
        idempotency_key=payload.idempotency_key,
        status=JournalEntryStatus.DRAFT,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(je)
    db.flush()

    for seq, ln in enumerate(payload.lines, start=1):
        db.add(JournalEntryLine(
            entry_id=je.id,
            account_id=ln.account_id,
            debit=ln.debit,
            credit=ln.credit,
            description=ln.description,
            cost_center_id=ln.cost_center_id,
            branch_id=ln.branch_id,
            sequence=seq,
        ))
    db.flush()
    return je


def post_journal_entry(
    db: Session,
    entry_id: int,
    company_id: int,
    actor_id: int | None,
) -> JournalEntry:
    je = _get_je_or_404(db, entry_id, company_id)

    if je.status == JournalEntryStatus.POSTED:
        return je  # idempotent
    if je.status != JournalEntryStatus.DRAFT:
        raise BusinessRuleViolation(
            f"Cannot post entry with status '{je.status}'"
        )

    settings = get_or_create_settings(db, company_id)
    if settings.require_manual_je_approval and je.source_module == SourceModule.MANUAL:
        _require_approval(
            db,
            company_id=company_id,
            reference_type="journal_entry",
            reference_id=je.id,
            request_type=ApprovalRequestType.MANUAL_JOURNAL_ENTRY,
            actor_id=actor_id,
            reason="Manual journal entry requires approval before posting",
        )

    _validate_and_post(db, je, company_id, actor_id)
    return je


def _require_approval(
    db: Session,
    company_id: int,
    reference_type: str,
    reference_id: int,
    request_type: ApprovalRequestType,
    actor_id: int | None,
    reason: str,
) -> None:
    approved = (
        db.query(ApprovalRequest)
        .filter_by(
            company_id=company_id,
            reference_type=reference_type,
            reference_id=reference_id,
            request_type=request_type,
            status=ApprovalStatus.APPROVED,
        )
        .first()
    )
    if approved:
        return

    pending = (
        db.query(ApprovalRequest)
        .filter_by(
            company_id=company_id,
            reference_type=reference_type,
            reference_id=reference_id,
            request_type=request_type,
            status=ApprovalStatus.PENDING,
        )
        .first()
    )
    if pending:
        raise ApprovalRequired(
            approval_request_id=pending.id,
            detail=reason,
        )

    req = ApprovalRequest(
        company_id=company_id,
        request_type=request_type,
        reference_type=reference_type,
        reference_id=reference_id,
        requested_by=actor_id,
        reason=reason,
        status=ApprovalStatus.PENDING,
    )
    db.add(req)
    db.flush()
    raise ApprovalRequired(approval_request_id=req.id, detail=reason)


def decide_approval(
    db: Session,
    approval_id: int,
    approve: bool,
    company_id: int,
    actor_id: int | None,
) -> ApprovalRequest:
    req = db.query(ApprovalRequest).filter_by(
        id=approval_id, company_id=company_id
    ).first()
    if req is None:
        raise NotFoundError("Approval request not found")
    if req.status != ApprovalStatus.PENDING:
        raise BusinessRuleViolation("Approval request is not PENDING")
    if req.requested_by == actor_id:
        raise BusinessRuleViolation("The requester cannot approve their own request")
    req.status = ApprovalStatus.APPROVED if approve else ApprovalStatus.REJECTED
    req.approved_by = actor_id
    req.decided_at = datetime.datetime.now(datetime.timezone.utc)
    db.flush()
    return req


def _validate_and_post(
    db: Session,
    je: JournalEntry,
    company_id: int,
    actor_id: int | None,
) -> None:
    lines = (
        db.query(JournalEntryLine)
        .filter_by(entry_id=je.id)
        .order_by(JournalEntryLine.sequence)
        .all()
    )
    if not lines:
        raise BusinessRuleViolation("Journal entry has no lines")

    total_debit = sum(ln.debit for ln in lines)
    total_credit = sum(ln.credit for ln in lines)
    if total_debit != total_credit:
        raise BusinessRuleViolation(
            f"Entry does not balance: debits {total_debit} ≠ credits {total_credit}"
        )

    for ln in lines:
        acct = db.query(Account).filter_by(
            id=ln.account_id, company_id=company_id, is_deleted=False
        ).first()
        if acct is None:
            raise BusinessRuleViolation(
                f"Account {ln.account_id} not found in this company"
            )
        if not acct.is_postable:
            raise BusinessRuleViolation(
                f"Account '{acct.code} {acct.name_en}' is not postable"
            )

    period = _resolve_period(db, company_id, je.entry_date)
    if period is None:
        raise BusinessRuleViolation(
            f"No open accounting period for date {je.entry_date}"
        )

    je.period_id = period.id
    je.status = JournalEntryStatus.POSTED
    je.updated_by = actor_id
    db.flush()


def reverse_journal_entry(
    db: Session,
    entry_id: int,
    reversal_date: datetime.date,
    company_id: int,
    actor_id: int | None,
    description: str | None = None,
) -> JournalEntry:
    original = _get_je_or_404(db, entry_id, company_id)
    if original.status == JournalEntryStatus.REVERSED:
        raise BusinessRuleViolation("Entry has already been reversed")
    if original.status != JournalEntryStatus.POSTED:
        raise BusinessRuleViolation("Only POSTED entries can be reversed")

    already = (
        db.query(JournalEntry)
        .filter_by(reversed_entry_id=original.id, company_id=company_id)
        .filter(JournalEntry.status != JournalEntryStatus.REVERSED)
        .first()
    )
    if already:
        raise BusinessRuleViolation("Entry has already been reversed")

    settings = get_or_create_settings(db, company_id)
    if settings.require_manual_je_approval and original.source_module == SourceModule.MANUAL:
        _require_approval(
            db,
            company_id=company_id,
            reference_type="reverse_journal_entry",
            reference_id=original.id,
            request_type=ApprovalRequestType.REVERSE_JOURNAL_ENTRY,
            actor_id=actor_id,
            reason="Journal entry reversal requires approval",
        )

    rev_number = _next_je_number(db, settings)
    rev = JournalEntry(
        company_id=company_id,
        entry_number=rev_number,
        entry_date=reversal_date,
        source_module=original.source_module,
        entry_type=EntryType.ADJUSTMENT,
        source_document=original.source_document,
        description=description or f"Reversal of {original.entry_number}",
        currency=original.currency,
        exchange_rate=original.exchange_rate,
        status=JournalEntryStatus.DRAFT,
        reversed_entry_id=original.id,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(rev)
    db.flush()

    orig_lines = (
        db.query(JournalEntryLine)
        .filter_by(entry_id=original.id)
        .order_by(JournalEntryLine.sequence)
        .all()
    )
    for ln in orig_lines:
        db.add(JournalEntryLine(
            entry_id=rev.id,
            account_id=ln.account_id,
            debit=ln.credit,   # swap sides: original credit → reversal debit
            credit=ln.debit,   # original debit → reversal credit
            description=ln.description,
            cost_center_id=ln.cost_center_id,
            branch_id=ln.branch_id,
            sequence=ln.sequence,
        ))
    db.flush()

    _validate_and_post(db, rev, company_id, actor_id)

    original.status = JournalEntryStatus.REVERSED
    original.updated_by = actor_id
    db.flush()
    return rev


def get_journal_entry(db: Session, entry_id: int, company_id: int) -> JournalEntry:
    return _get_je_or_404(db, entry_id, company_id)


def list_journal_entries(
    db: Session,
    company_id: int,
    status: JournalEntryStatus | None = None,
    from_date: datetime.date | None = None,
    to_date: datetime.date | None = None,
) -> list[JournalEntry]:
    q = db.query(JournalEntry).filter_by(company_id=company_id)
    if status:
        q = q.filter(JournalEntry.status == status)
    if from_date:
        q = q.filter(JournalEntry.entry_date >= from_date)
    if to_date:
        q = q.filter(JournalEntry.entry_date <= to_date)
    return q.order_by(JournalEntry.entry_date, JournalEntry.id).all()


def _get_je_or_404(db: Session, entry_id: int, company_id: int) -> JournalEntry:
    je = db.query(JournalEntry).filter_by(id=entry_id, company_id=company_id).first()
    if je is None:
        raise NotFoundError(f"Journal entry {entry_id} not found")
    return je


def _next_je_number(db: Session, settings: AccountingSettings) -> str:
    """Race-safe sequence via SELECT FOR UPDATE on the settings row."""
    locked = (
        db.execute(
            select(AccountingSettings)
            .where(AccountingSettings.id == settings.id)
            .with_for_update()
        )
        .scalar_one()
    )
    locked.last_je_number += 1
    db.flush()
    return f"{locked.je_prefix}-{locked.last_je_number:06d}"


# ===========================================================================
# PostingService — Isolated Engine
# ===========================================================================


@dataclass
class PostingEvent:
    """Input contract for the PostingService.

    Swap the call site to async by publishing this dataclass on a broker;
    this file stays unchanged.
    """

    event_type: str
    payload: dict[str, Any]
    entry_date: datetime.date
    company_id: int
    actor_id: int | None
    idempotency_key: str
    source_document: str | None = None
    entry_type: EntryType = EntryType.STANDARD


@dataclass
class PostingResult:
    journal_entry_id: int
    entry_number: str
    was_idempotent: bool = False


class PostingService:
    """Fully isolated posting engine.

    MUST NOT import from sales, purchasing, or inventory modules.
    The contract test in test_accounting.py asserts this.
    """

    def post(self, db: Session, event: PostingEvent) -> PostingResult:
        # Stage 1: idempotency
        existing = self._check_idempotency(db, event)
        if existing:
            return PostingResult(
                journal_entry_id=existing.id,
                entry_number=existing.entry_number,
                was_idempotent=True,
            )

        # Stage 2: resolve template
        template = _resolve_template(db, event.company_id, event.event_type, event.entry_date)
        if template is None:
            raise BusinessRuleViolation(
                f"No active posting template for event '{event.event_type}'"
            )

        # Stage 3: generate raw lines
        raw_lines = self._generate_lines(db, event, template)

        # Stage 4: validate balance
        self._validate_balance(raw_lines)

        # Stage 5: resolve accounts
        account_map = self._resolve_accounts(db, event.company_id, raw_lines)

        # Stage 6: resolve period
        period = _resolve_period(db, event.company_id, event.entry_date)
        if period is None:
            raise BusinessRuleViolation(
                f"No open accounting period for date {event.entry_date}"
            )

        # Stage 7: save and post
        je = self._save_and_post(db, event, raw_lines, account_map, period, template)
        return PostingResult(journal_entry_id=je.id, entry_number=je.entry_number)

    def _check_idempotency(
        self, db: Session, event: PostingEvent
    ) -> JournalEntry | None:
        return (
            db.query(JournalEntry)
            .filter_by(
                idempotency_key=event.idempotency_key,
                company_id=event.company_id,
            )
            .first()
        )

    def _generate_lines(
        self,
        db: Session,
        event: PostingEvent,
        template: PostingTemplateHeader,
    ) -> list[dict]:
        tlines = (
            db.query(PostingTemplateLine)
            .filter_by(header_id=template.id)
            .order_by(PostingTemplateLine.sequence)
            .all()
        )
        result = []
        for tl in tlines:
            amount = self._resolve_amount(event.payload, tl.amount_source)
            account_code = self._resolve_account_code(event.payload, tl)
            result.append({
                "account_code": account_code,
                "side": tl.side,
                "amount": amount,
                "sequence": tl.sequence,
            })
        return result

    def _resolve_amount(self, payload: dict, amount_source: str) -> Decimal:
        parts = amount_source.split(".")
        cur: Any = payload
        for p in parts:
            if not isinstance(cur, dict):
                raise BusinessRuleViolation(
                    f"Amount source '{amount_source}' cannot be resolved"
                )
            cur = cur.get(p)
            if cur is None:
                raise BusinessRuleViolation(
                    f"Amount source '{amount_source}' not found in payload"
                )
        return Decimal(str(cur))

    def _resolve_account_code(self, payload: dict, tl: PostingTemplateLine) -> str:
        if tl.selector_type == AccountSelectorType.FIXED_CODE:
            return tl.selector_param
        if tl.selector_type == AccountSelectorType.PAYLOAD_ACCOUNT_CODE:
            code = payload.get(tl.selector_param)
            if code is None:
                raise BusinessRuleViolation(
                    f"Payload field '{tl.selector_param}' for account code missing"
                )
            return str(code)
        if tl.selector_type == AccountSelectorType.PAYLOAD_ACCOUNT_ID:
            acct_id = payload.get(tl.selector_param)
            if acct_id is None:
                raise BusinessRuleViolation(
                    f"Payload field '{tl.selector_param}' for account ID missing"
                )
            return f"__ID__{acct_id}"
        # Semantic selectors: selector_param is the payload key with the account code
        code = payload.get(tl.selector_param)
        if code is None:
            raise BusinessRuleViolation(
                f"Semantic selector '{tl.selector_type}' key '{tl.selector_param}' "
                "not found in payload"
            )
        return str(code)

    def _validate_balance(self, lines: list[dict]) -> None:
        total_dr = sum(ln["amount"] for ln in lines if ln["side"] == "DEBIT")
        total_cr = sum(ln["amount"] for ln in lines if ln["side"] == "CREDIT")
        if total_dr != total_cr:
            raise BusinessRuleViolation(
                f"Template produces unbalanced entry: debits {total_dr} ≠ credits {total_cr}"
            )

    def _resolve_accounts(
        self, db: Session, company_id: int, lines: list[dict]
    ) -> dict[str, Account]:
        result: dict[str, Account] = {}
        for ln in lines:
            code = ln["account_code"]
            if code in result:
                continue
            if code.startswith("__ID__"):
                acct_id = int(code[6:])
                acct = db.query(Account).filter_by(
                    id=acct_id, company_id=company_id, is_deleted=False
                ).first()
            else:
                acct = db.query(Account).filter_by(
                    code=code, company_id=company_id, is_deleted=False
                ).first()
            if acct is None:
                raise BusinessRuleViolation(
                    f"Account '{code}' not found in company {company_id}"
                )
            if not acct.is_postable:
                raise BusinessRuleViolation(f"Account '{acct.code}' is not postable")
            result[code] = acct
        return result

    def _save_and_post(
        self,
        db: Session,
        event: PostingEvent,
        raw_lines: list[dict],
        account_map: dict[str, Account],
        period: AccountingPeriod,
        template: PostingTemplateHeader,
    ) -> JournalEntry:
        settings = get_or_create_settings(db, event.company_id)
        entry_number = _next_je_number(db, settings)

        je = JournalEntry(
            company_id=event.company_id,
            entry_number=entry_number,
            entry_date=event.entry_date,
            period_id=period.id,
            source_module=SourceModule.SYSTEM,
            entry_type=event.entry_type,
            source_document=event.source_document,
            description=f"Auto-posted: {event.event_type}",
            currency="KWD",
            idempotency_key=event.idempotency_key,
            status=JournalEntryStatus.POSTED,
            posting_template_id=template.id,
            created_by=event.actor_id,
            updated_by=event.actor_id,
        )
        db.add(je)
        db.flush()

        for seq, ln in enumerate(raw_lines, start=1):
            acct = account_map[ln["account_code"]]
            db.add(JournalEntryLine(
                entry_id=je.id,
                account_id=acct.id,
                debit=ln["amount"] if ln["side"] == "DEBIT" else Decimal("0"),
                credit=ln["amount"] if ln["side"] == "CREDIT" else Decimal("0"),
                sequence=seq,
            ))
        db.flush()
        return je


# Module-level singleton (synchronous interface; swap call site for async)
posting_service = PostingService()


# ===========================================================================
# Reports  (all computed from journal_entry_lines — NO stored balances)
# ===========================================================================


def get_trial_balance(
    db: Session,
    company_id: int,
    as_of_date: datetime.date,
    cost_center_id: int | None = None,
) -> schemas.TrialBalanceReport:
    q = (
        db.query(
            Account.id.label("account_id"),
            Account.code.label("account_code"),
            Account.name_en.label("account_name"),
            Account.account_type.label("account_type"),
            func.coalesce(func.sum(JournalEntryLine.debit), 0).label("total_debit"),
            func.coalesce(func.sum(JournalEntryLine.credit), 0).label("total_credit"),
        )
        .join(JournalEntryLine, JournalEntryLine.account_id == Account.id)
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.entry_id)
        .filter(
            Account.company_id == company_id,
            Account.is_deleted == False,  # noqa: E712
            JournalEntry.company_id == company_id,
            JournalEntry.status == JournalEntryStatus.POSTED,
            JournalEntry.entry_date <= as_of_date,
        )
    )
    if cost_center_id is not None:
        q = q.filter(JournalEntryLine.cost_center_id == cost_center_id)
    rows = (
        q.group_by(Account.id, Account.code, Account.name_en, Account.account_type)
        .order_by(Account.code)
        .all()
    )

    lines = []
    grand_dr = Decimal("0")
    grand_cr = Decimal("0")
    for row in rows:
        d = Decimal(str(row.total_debit))
        c = Decimal(str(row.total_credit))
        lines.append(schemas.TrialBalanceLine(
            account_id=row.account_id,
            account_code=row.account_code,
            account_name=row.account_name,
            account_type=row.account_type,
            total_debit=d,
            total_credit=c,
            balance=d - c,
        ))
        grand_dr += d
        grand_cr += c

    return schemas.TrialBalanceReport(
        as_of_date=as_of_date,
        lines=lines,
        grand_total_debit=grand_dr,
        grand_total_credit=grand_cr,
        is_balanced=(grand_dr == grand_cr),
    )


def get_pl(
    db: Session,
    company_id: int,
    from_date: datetime.date,
    to_date: datetime.date,
    cost_center_id: int | None = None,
) -> schemas.PLReport:
    q = (
        db.query(
            Account.id.label("account_id"),
            Account.code.label("account_code"),
            Account.name_en.label("account_name"),
            Account.account_type.label("account_type"),
            func.coalesce(func.sum(JournalEntryLine.debit), 0).label("total_debit"),
            func.coalesce(func.sum(JournalEntryLine.credit), 0).label("total_credit"),
        )
        .join(JournalEntryLine, JournalEntryLine.account_id == Account.id)
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.entry_id)
        .filter(
            Account.company_id == company_id,
            Account.is_deleted == False,  # noqa: E712
            Account.account_type.in_([AccountType.REVENUE, AccountType.EXPENSE]),
            JournalEntry.company_id == company_id,
            JournalEntry.status == JournalEntryStatus.POSTED,
            JournalEntry.entry_date >= from_date,
            JournalEntry.entry_date <= to_date,
        )
    )
    if cost_center_id is not None:
        q = q.filter(JournalEntryLine.cost_center_id == cost_center_id)
    rows = (
        q.group_by(Account.id, Account.code, Account.name_en, Account.account_type)
        .order_by(Account.code)
        .all()
    )

    rev_lines: list[schemas.PLLine] = []
    exp_lines: list[schemas.PLLine] = []
    total_rev = Decimal("0")
    total_exp = Decimal("0")

    for row in rows:
        d = Decimal(str(row.total_debit))
        c = Decimal(str(row.total_credit))
        if row.account_type == AccountType.REVENUE:
            net = c - d
            rev_lines.append(schemas.PLLine(
                account_id=row.account_id,
                account_code=row.account_code,
                account_name=row.account_name,
                account_type=row.account_type,
                net_amount=net,
            ))
            total_rev += net
        else:
            net = d - c
            exp_lines.append(schemas.PLLine(
                account_id=row.account_id,
                account_code=row.account_code,
                account_name=row.account_name,
                account_type=row.account_type,
                net_amount=net,
            ))
            total_exp += net

    return schemas.PLReport(
        from_date=from_date,
        to_date=to_date,
        revenue_lines=rev_lines,
        expense_lines=exp_lines,
        total_revenue=total_rev,
        total_expenses=total_exp,
        net_income=total_rev - total_exp,
    )


def get_balance_sheet(
    db: Session,
    company_id: int,
    as_of_date: datetime.date,
) -> schemas.BalanceSheetReport:
    rows = (
        db.query(
            Account.id.label("account_id"),
            Account.code.label("account_code"),
            Account.name_en.label("account_name"),
            Account.account_type.label("account_type"),
            func.coalesce(func.sum(JournalEntryLine.debit), 0).label("total_debit"),
            func.coalesce(func.sum(JournalEntryLine.credit), 0).label("total_credit"),
        )
        .join(JournalEntryLine, JournalEntryLine.account_id == Account.id)
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.entry_id)
        .filter(
            Account.company_id == company_id,
            Account.is_deleted == False,  # noqa: E712
            JournalEntry.company_id == company_id,
            JournalEntry.status == JournalEntryStatus.POSTED,
            JournalEntry.entry_date <= as_of_date,
        )
        .group_by(Account.id, Account.code, Account.name_en, Account.account_type)
        .order_by(Account.code)
        .all()
    )

    assets: list[schemas.BalanceSheetLine] = []
    liabilities: list[schemas.BalanceSheetLine] = []
    equity: list[schemas.BalanceSheetLine] = []
    total_assets = Decimal("0")
    total_liabilities = Decimal("0")
    total_equity_paid_in = Decimal("0")
    retained_earnings = Decimal("0")

    for row in rows:
        d = Decimal(str(row.total_debit))
        c = Decimal(str(row.total_credit))

        if row.account_type == AccountType.ASSET:
            balance = d - c
            assets.append(schemas.BalanceSheetLine(
                account_id=row.account_id,
                account_code=row.account_code,
                account_name=row.account_name,
                balance=balance,
            ))
            total_assets += balance
        elif row.account_type == AccountType.LIABILITY:
            balance = c - d
            liabilities.append(schemas.BalanceSheetLine(
                account_id=row.account_id,
                account_code=row.account_code,
                account_name=row.account_name,
                balance=balance,
            ))
            total_liabilities += balance
        elif row.account_type == AccountType.EQUITY:
            balance = c - d
            equity.append(schemas.BalanceSheetLine(
                account_id=row.account_id,
                account_code=row.account_code,
                account_name=row.account_name,
                balance=balance,
            ))
            total_equity_paid_in += balance
        elif row.account_type == AccountType.REVENUE:
            # Net revenue flows into retained earnings (credit-normal)
            retained_earnings += c - d
        elif row.account_type == AccountType.EXPENSE:
            # Net expense reduces retained earnings (debit-normal)
            retained_earnings -= d - c

    total_equity = total_equity_paid_in + retained_earnings
    is_balanced = total_assets == (total_liabilities + total_equity)

    return schemas.BalanceSheetReport(
        as_of_date=as_of_date,
        assets=assets,
        liabilities=liabilities,
        equity=equity,
        retained_earnings=retained_earnings,
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        total_equity_paid_in=total_equity_paid_in,
        total_equity=total_equity,
        is_balanced=is_balanced,
    )


def get_gl(
    db: Session,
    account_id: int,
    company_id: int,
    from_date: datetime.date,
    to_date: datetime.date,
) -> schemas.GLReport:
    acct = _get_account_or_404(db, account_id, company_id)

    ob_row = (
        db.query(
            func.coalesce(func.sum(JournalEntryLine.debit), 0).label("d"),
            func.coalesce(func.sum(JournalEntryLine.credit), 0).label("c"),
        )
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.entry_id)
        .filter(
            JournalEntryLine.account_id == account_id,
            JournalEntry.company_id == company_id,
            JournalEntry.status == JournalEntryStatus.POSTED,
            JournalEntry.entry_date < from_date,
        )
        .first()
    )
    opening_balance = Decimal(str(ob_row.d)) - Decimal(str(ob_row.c))

    rows = (
        db.query(
            JournalEntry.id.label("entry_id"),
            JournalEntry.entry_number,
            JournalEntry.entry_date,
            JournalEntry.source_document,
            JournalEntry.description,
            JournalEntryLine.description.label("line_description"),
            JournalEntryLine.debit,
            JournalEntryLine.credit,
        )
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.entry_id)
        .filter(
            JournalEntryLine.account_id == account_id,
            JournalEntry.company_id == company_id,
            JournalEntry.status == JournalEntryStatus.POSTED,
            JournalEntry.entry_date >= from_date,
            JournalEntry.entry_date <= to_date,
        )
        .order_by(JournalEntry.entry_date, JournalEntry.id)
        .all()
    )

    entries: list[schemas.GLEntry] = []
    running = opening_balance
    for row in rows:
        d = Decimal(str(row.debit))
        c = Decimal(str(row.credit))
        running += d - c
        entries.append(schemas.GLEntry(
            entry_id=row.entry_id,
            entry_number=row.entry_number,
            entry_date=row.entry_date,
            source_document=row.source_document,
            description=row.description,
            line_description=row.line_description,
            debit=d,
            credit=c,
            running_balance=running,
        ))

    return schemas.GLReport(
        account_id=acct.id,
        account_code=acct.code,
        account_name=acct.name_en,
        account_type=acct.account_type,
        from_date=from_date,
        to_date=to_date,
        opening_balance=opening_balance,
        entries=entries,
        closing_balance=running,
    )
