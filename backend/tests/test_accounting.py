"""Accounting module tests.

Covers: settings, CoA template apply, account hierarchy + cycle guard +
in-use-delete guard, fiscal year + period lifecycle, posting template
resolution (global vs company), posting engine pipeline (balance, accounts,
period), manual JE + maker-checker, reversal (exact opposite), idempotency,
closed-period rejection + reopen approval, Trial Balance, P&L, Balance Sheet
(assets == liabilities + equity including retained earnings), GL, engine
isolation contract.

All tests run in a rolled-back transaction — nothing persists.
"""

import ast
import datetime
import importlib
import importlib.util
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from app.core.exceptions import ApprovalRequired, BusinessRuleViolation, NotFoundError
from app.modules.accounting import schemas, service
from app.modules.accounting.models import (
    AccountType,
    EntryType,
    FiscalYearStatus,
    JournalEntryStatus,
    PeriodStatus,
)
from app.modules.auth import schemas as auth_schemas
from app.modules.auth import service as auth_service
from app.modules.organization import schemas as org_schemas
from app.modules.organization import service as org_service
from app.modules.organization.models import BranchType
from app.modules.shared.models import ApprovalStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _company(db, code="ACCTCO"):
    return org_service.create_company(
        db,
        org_schemas.CompanyCreate(
            code=code,
            name_en=f"{code} Ltd",
            name_ar=f"شركة {code}",
            commercial_registration_no=f"CR-{code}",
        ),
    )


def _user(db, company_id, username="acct_user", superuser=False):
    return auth_service.create_user(
        db,
        auth_schemas.UserCreate(
            username=username,
            email=f"{username}@test.com",
            full_name_en=username,
            full_name_ar=username,
            password="Pass1234!",
            is_superuser=superuser,
        ),
        company_id=company_id,
        actor_id=None,
    )


def _fy(db, company_id, actor_id=None):
    return service.create_fiscal_year(
        db,
        schemas.FiscalYearCreate(
            code="FY2026",
            name_en="FY 2026",
            name_ar="السنة المالية 2026",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31),
        ),
        company_id=company_id,
        actor_id=actor_id,
    )


def _periods(db, company_id, fy_id, actor_id=None):
    return service.generate_periods(
        db,
        schemas.GeneratePeriodsRequest(fiscal_year_id=fy_id, count=12),
        company_id=company_id,
        actor_id=actor_id,
    )


def _accounts(db, company_id, actor_id=None):
    """Create the minimal accounts needed for JE tests."""
    defs = [
        ("1100", "Bank",            "البنك",             AccountType.ASSET,     True),
        ("1200", "AR",              "مدينون تجاريون",    AccountType.ASSET,     True),
        ("1300", "Equipment",       "معدات",             AccountType.ASSET,     True),
        ("2100", "AP",              "دائنون تجاريون",    AccountType.LIABILITY,  True),
        ("2200", "Bank Loan",       "قرض بنكي",          AccountType.LIABILITY,  True),
        ("3100", "Share Capital",   "رأس المال",         AccountType.EQUITY,    True),
        ("4100", "Sales Revenue",   "إيرادات المبيعات",  AccountType.REVENUE,   True),
        ("5100", "COGS",            "تكلفة البضاعة",     AccountType.EXPENSE,   True),
        ("6100", "Salaries",        "رواتب",             AccountType.EXPENSE,   True),
        # header (non-postable)
        ("9000", "Header Acct",     "حساب رئيسي",        AccountType.ASSET,     False),
    ]
    result = {}
    for code, name_en, name_ar, atype, postable in defs:
        a = service.create_account(
            db,
            schemas.AccountCreate(
                code=code,
                name_en=name_en,
                name_ar=name_ar,
                account_type=atype,
                is_postable=postable,
            ),
            company_id=company_id,
            actor_id=actor_id,
        )
        result[code] = a
    return result


def _ctx(db, company_code="ACCTCO"):
    """Full accounting context with company, users, FY, periods, accounts."""
    co = _company(db, company_code)
    maker = _user(db, co.id, "maker")
    checker = _user(db, co.id, "checker")
    fy = _fy(db, co.id, maker.id)
    periods = _periods(db, co.id, fy.id, maker.id)
    accts = _accounts(db, co.id, maker.id)
    return {
        "company": co,
        "maker": maker,
        "checker": checker,
        "fy": fy,
        "periods": periods,
        "accts": accts,
    }


def _je(db, company_id, accts, actor_id=None, entry_date=None, idempotency_key=None):
    """Post a balanced manual JE: Dr Bank 1000 / Cr Share Capital 1000."""
    date = entry_date or datetime.date(2026, 1, 15)
    je = service.create_journal_entry(
        db,
        schemas.JournalEntryCreate(
            entry_date=date,
            description="Test entry",
            idempotency_key=idempotency_key,
            lines=[
                schemas.JournalEntryLineCreate(
                    account_id=accts["1100"].id, debit=Decimal("1000")
                ),
                schemas.JournalEntryLineCreate(
                    account_id=accts["3100"].id, credit=Decimal("1000")
                ),
            ],
        ),
        company_id=company_id,
        actor_id=actor_id,
    )
    service.post_journal_entry(db, je.id, company_id, actor_id)
    return je


# ===========================================================================
# Settings
# ===========================================================================


def test_get_or_create_settings(db_session):
    co = _company(db_session)
    s = service.get_or_create_settings(db_session, co.id)
    assert s.company_id == co.id
    assert s.je_prefix == "JE"
    assert s.last_je_number == 0
    assert not s.require_manual_je_approval


def test_update_settings(db_session):
    co = _company(db_session)
    s = service.update_settings(
        db_session,
        schemas.AccountingSettingsUpdate(je_prefix="ACC", require_manual_je_approval=True),
        co.id,
        actor_id=None,
    )
    assert s.je_prefix == "ACC"
    assert s.require_manual_je_approval is True


# ===========================================================================
# Chart of Accounts
# ===========================================================================


def test_create_account(db_session):
    co = _company(db_session)
    a = service.create_account(
        db_session,
        schemas.AccountCreate(
            code="1010", name_en="Cash", name_ar="نقدية",
            account_type=AccountType.ASSET,
        ),
        co.id, None,
    )
    assert a.code == "1010"
    assert a.account_type == AccountType.ASSET
    assert a.is_postable is True


def test_account_hierarchy(db_session):
    co = _company(db_session)
    parent = service.create_account(
        db_session,
        schemas.AccountCreate(
            code="1000", name_en="Assets", name_ar="الأصول",
            account_type=AccountType.ASSET, is_postable=False,
        ),
        co.id, None,
    )
    child = service.create_account(
        db_session,
        schemas.AccountCreate(
            code="1010", name_en="Cash", name_ar="نقدية",
            account_type=AccountType.ASSET, parent_id=parent.id,
        ),
        co.id, None,
    )
    assert child.parent_id == parent.id


def test_account_cycle_rejected(db_session):
    co = _company(db_session)
    a = service.create_account(
        db_session,
        schemas.AccountCreate(
            code="A1", name_en="A1", name_ar="A1", account_type=AccountType.ASSET
        ),
        co.id, None,
    )
    b = service.create_account(
        db_session,
        schemas.AccountCreate(
            code="A2", name_en="A2", name_ar="A2",
            account_type=AccountType.ASSET, parent_id=a.id,
        ),
        co.id, None,
    )
    # Making A1's parent = B would create a cycle A1→A2→A1
    with pytest.raises(BusinessRuleViolation, match="cycle"):
        service.update_account(
            db_session,
            a.id,
            schemas.AccountUpdate(parent_id=b.id),
            co.id, None,
        )


def test_delete_account_in_use_rejected(db_session):
    ctx = _ctx(db_session, "DELTEST")
    co = ctx["company"]
    accts = ctx["accts"]
    maker = ctx["maker"]
    # Post a JE that touches accts["1100"]
    _je(db_session, co.id, accts, actor_id=maker.id)
    with pytest.raises(BusinessRuleViolation, match="used in journal entries"):
        service.delete_account(db_session, accts["1100"].id, co.id, None)


def test_delete_account_with_children_rejected(db_session):
    co = _company(db_session, "DELCH")
    parent = service.create_account(
        db_session,
        schemas.AccountCreate(
            code="P1", name_en="P", name_ar="P",
            account_type=AccountType.ASSET, is_postable=False,
        ),
        co.id, None,
    )
    service.create_account(
        db_session,
        schemas.AccountCreate(
            code="C1", name_en="C", name_ar="C",
            account_type=AccountType.ASSET, parent_id=parent.id,
        ),
        co.id, None,
    )
    with pytest.raises(BusinessRuleViolation, match="child accounts"):
        service.delete_account(db_session, parent.id, co.id, None)


def test_apply_coa_template_twice_rejected(db_session):
    co = _company(db_session, "TPLTWICE")
    # Create a minimal template manually
    from app.modules.accounting.models import CoATemplate, CoATemplateLine
    tmpl = CoATemplate(code="MINI", name_en="Mini", name_ar="صغير")
    db_session.add(tmpl)
    db_session.flush()
    db_session.add(CoATemplateLine(
        template_id=tmpl.id, code="1010", name_en="Cash", name_ar="نقدية",
        account_type=AccountType.ASSET, sequence=1, is_postable=True,
    ))
    db_session.flush()

    service.apply_coa_template(db_session, co.id, "MINI", None)
    with pytest.raises(BusinessRuleViolation, match="already exists"):
        service.apply_coa_template(db_session, co.id, "MINI", None)


def test_cross_company_account_404(db_session):
    co1 = _company(db_session, "XCOMP1")
    co2 = _company(db_session, "XCOMP2")
    a = service.create_account(
        db_session,
        schemas.AccountCreate(
            code="1010", name_en="Cash", name_ar="نقدية",
            account_type=AccountType.ASSET,
        ),
        co1.id, None,
    )
    with pytest.raises(NotFoundError):
        service.get_account(db_session, a.id, co2.id)


# ===========================================================================
# Fiscal Year / Period
# ===========================================================================


def test_create_fiscal_year(db_session):
    co = _company(db_session, "FYCO")
    fy = _fy(db_session, co.id)
    assert fy.code == "FY2026"
    assert fy.status == FiscalYearStatus.OPEN


def test_generate_12_monthly_periods(db_session):
    co = _company(db_session, "PERIOD12")
    fy = _fy(db_session, co.id)
    periods = _periods(db_session, co.id, fy.id)
    assert len(periods) == 12
    assert periods[0].name_en == "January 2026"
    assert periods[11].name_en == "December 2026"
    assert periods[0].start_date == datetime.date(2026, 1, 1)
    assert periods[11].end_date == datetime.date(2026, 12, 31)


def test_close_period(db_session):
    co = _company(db_session, "CLPER")
    fy = _fy(db_session, co.id)
    periods = _periods(db_session, co.id, fy.id)
    p = service.close_period(db_session, periods[0].id, co.id, None)
    assert p.status == PeriodStatus.CLOSED


def test_close_period_twice_rejected(db_session):
    co = _company(db_session, "CLPER2")
    fy = _fy(db_session, co.id)
    periods = _periods(db_session, co.id, fy.id)
    service.close_period(db_session, periods[0].id, co.id, None)
    with pytest.raises(BusinessRuleViolation, match="already closed"):
        service.close_period(db_session, periods[0].id, co.id, None)


def test_reopen_period_requires_approval(db_session):
    co = _company(db_session, "REOPEN")
    maker = _user(db_session, co.id, "reopen_maker")
    fy = _fy(db_session, co.id, maker.id)
    periods = _periods(db_session, co.id, fy.id, maker.id)
    service.close_period(db_session, periods[0].id, co.id, maker.id)

    with pytest.raises(ApprovalRequired) as exc_info:
        service.reopen_period(db_session, periods[0].id, co.id, maker.id)
    req_id = exc_info.value.approval_request_id

    checker = _user(db_session, co.id, "reopen_checker")
    service.decide_approval(db_session, req_id, True, co.id, checker.id)

    p = service.reopen_period(db_session, periods[0].id, co.id, maker.id)
    assert p.status == PeriodStatus.REOPENED


def test_cannot_approve_own_period_reopen(db_session):
    co = _company(db_session, "SELFAPP")
    maker = _user(db_session, co.id, "self_maker")
    fy = _fy(db_session, co.id, maker.id)
    periods = _periods(db_session, co.id, fy.id, maker.id)
    service.close_period(db_session, periods[0].id, co.id, maker.id)

    with pytest.raises(ApprovalRequired) as exc_info:
        service.reopen_period(db_session, periods[0].id, co.id, maker.id)
    req_id = exc_info.value.approval_request_id

    with pytest.raises(BusinessRuleViolation, match="requester cannot approve"):
        service.decide_approval(db_session, req_id, True, co.id, maker.id)


# ===========================================================================
# Journal Entry — basic lifecycle
# ===========================================================================


def test_create_and_post_je(db_session):
    ctx = _ctx(db_session, "JE1")
    co = ctx["company"]
    accts = ctx["accts"]
    maker = ctx["maker"]

    je = service.create_journal_entry(
        db_session,
        schemas.JournalEntryCreate(
            entry_date=datetime.date(2026, 1, 15),
            description="Opening capital",
            lines=[
                schemas.JournalEntryLineCreate(
                    account_id=accts["1100"].id, debit=Decimal("10000")
                ),
                schemas.JournalEntryLineCreate(
                    account_id=accts["3100"].id, credit=Decimal("10000")
                ),
            ],
        ),
        company_id=co.id,
        actor_id=maker.id,
    )
    assert je.status == JournalEntryStatus.DRAFT

    posted = service.post_journal_entry(db_session, je.id, co.id, maker.id)
    assert posted.status == JournalEntryStatus.POSTED
    assert posted.period_id is not None


def test_post_je_idempotent(db_session):
    ctx = _ctx(db_session, "IDEMPOST")
    co = ctx["company"]
    accts = ctx["accts"]
    maker = ctx["maker"]
    je = service.create_journal_entry(
        db_session,
        schemas.JournalEntryCreate(
            entry_date=datetime.date(2026, 1, 15),
            lines=[
                schemas.JournalEntryLineCreate(
                    account_id=accts["1100"].id, debit=Decimal("500")
                ),
                schemas.JournalEntryLineCreate(
                    account_id=accts["3100"].id, credit=Decimal("500")
                ),
            ],
        ),
        co.id, maker.id,
    )
    service.post_journal_entry(db_session, je.id, co.id, maker.id)
    # Second call should return the same posted entry without error
    result = service.post_journal_entry(db_session, je.id, co.id, maker.id)
    assert result.status == JournalEntryStatus.POSTED
    assert result.id == je.id


def test_unbalanced_je_rejected(db_session):
    ctx = _ctx(db_session, "UNBAL")
    co = ctx["company"]
    accts = ctx["accts"]
    je = service.create_journal_entry(
        db_session,
        schemas.JournalEntryCreate(
            entry_date=datetime.date(2026, 1, 15),
            lines=[
                schemas.JournalEntryLineCreate(
                    account_id=accts["1100"].id, debit=Decimal("1000")
                ),
                schemas.JournalEntryLineCreate(
                    account_id=accts["3100"].id, credit=Decimal("999")
                ),
            ],
        ),
        co.id, None,
    )
    with pytest.raises(BusinessRuleViolation, match="balance"):
        service.post_journal_entry(db_session, je.id, co.id, None)


def test_non_postable_account_rejected(db_session):
    ctx = _ctx(db_session, "NOPOST")
    co = ctx["company"]
    accts = ctx["accts"]
    je = service.create_journal_entry(
        db_session,
        schemas.JournalEntryCreate(
            entry_date=datetime.date(2026, 1, 15),
            lines=[
                schemas.JournalEntryLineCreate(
                    account_id=accts["9000"].id, debit=Decimal("500")
                ),
                schemas.JournalEntryLineCreate(
                    account_id=accts["3100"].id, credit=Decimal("500")
                ),
            ],
        ),
        co.id, None,
    )
    with pytest.raises(BusinessRuleViolation, match="not postable"):
        service.post_journal_entry(db_session, je.id, co.id, None)


def test_closed_period_rejects_posting(db_session):
    ctx = _ctx(db_session, "CLPOST")
    co = ctx["company"]
    accts = ctx["accts"]
    periods = ctx["periods"]
    # Close all periods
    for p in periods:
        service.close_period(db_session, p.id, co.id, None)

    je = service.create_journal_entry(
        db_session,
        schemas.JournalEntryCreate(
            entry_date=datetime.date(2026, 1, 15),
            lines=[
                schemas.JournalEntryLineCreate(
                    account_id=accts["1100"].id, debit=Decimal("100")
                ),
                schemas.JournalEntryLineCreate(
                    account_id=accts["3100"].id, credit=Decimal("100")
                ),
            ],
        ),
        co.id, None,
    )
    with pytest.raises(BusinessRuleViolation, match="No open accounting period"):
        service.post_journal_entry(db_session, je.id, co.id, None)


def test_schema_rejects_both_sides_nonzero(db_session):
    with pytest.raises(Exception, match="cannot have both debit and credit"):
        schemas.JournalEntryLineCreate(
            account_id=1,
            debit=Decimal("100"),
            credit=Decimal("100"),
        )


def test_schema_rejects_both_sides_zero(db_session):
    with pytest.raises(Exception, match="must have debit > 0 or credit > 0"):
        schemas.JournalEntryLineCreate(
            account_id=1,
            debit=Decimal("0"),
            credit=Decimal("0"),
        )


# ===========================================================================
# Idempotency key
# ===========================================================================


def test_idempotency_key_deduplication(db_session):
    ctx = _ctx(db_session, "IDEM1")
    co = ctx["company"]
    accts = ctx["accts"]
    maker = ctx["maker"]

    payload = schemas.JournalEntryCreate(
        entry_date=datetime.date(2026, 1, 15),
        idempotency_key="unique-key-001",
        lines=[
            schemas.JournalEntryLineCreate(
                account_id=accts["1100"].id, debit=Decimal("200")
            ),
            schemas.JournalEntryLineCreate(
                account_id=accts["3100"].id, credit=Decimal("200")
            ),
        ],
    )
    je1 = service.create_journal_entry(db_session, payload, co.id, maker.id)
    je2 = service.create_journal_entry(db_session, payload, co.id, maker.id)
    assert je1.id == je2.id


# ===========================================================================
# Maker-checker for manual JE
# ===========================================================================


def test_manual_je_maker_checker(db_session):
    ctx = _ctx(db_session, "MKCJK")
    co = ctx["company"]
    accts = ctx["accts"]
    maker = ctx["maker"]
    checker = ctx["checker"]

    service.update_settings(
        db_session,
        schemas.AccountingSettingsUpdate(require_manual_je_approval=True),
        co.id, None,
    )

    je = service.create_journal_entry(
        db_session,
        schemas.JournalEntryCreate(
            entry_date=datetime.date(2026, 1, 15),
            lines=[
                schemas.JournalEntryLineCreate(
                    account_id=accts["1100"].id, debit=Decimal("5000")
                ),
                schemas.JournalEntryLineCreate(
                    account_id=accts["3100"].id, credit=Decimal("5000")
                ),
            ],
        ),
        co.id, maker.id,
    )

    with pytest.raises(ApprovalRequired) as exc_info:
        service.post_journal_entry(db_session, je.id, co.id, maker.id)
    req_id = exc_info.value.approval_request_id

    service.decide_approval(db_session, req_id, True, co.id, checker.id)
    posted = service.post_journal_entry(db_session, je.id, co.id, maker.id)
    assert posted.status == JournalEntryStatus.POSTED


def test_maker_cannot_approve_own_je(db_session):
    ctx = _ctx(db_session, "SELFJE")
    co = ctx["company"]
    accts = ctx["accts"]
    maker = ctx["maker"]

    service.update_settings(
        db_session,
        schemas.AccountingSettingsUpdate(require_manual_je_approval=True),
        co.id, None,
    )

    je = service.create_journal_entry(
        db_session,
        schemas.JournalEntryCreate(
            entry_date=datetime.date(2026, 1, 15),
            lines=[
                schemas.JournalEntryLineCreate(
                    account_id=accts["1100"].id, debit=Decimal("100")
                ),
                schemas.JournalEntryLineCreate(
                    account_id=accts["3100"].id, credit=Decimal("100")
                ),
            ],
        ),
        co.id, maker.id,
    )

    with pytest.raises(ApprovalRequired) as exc_info:
        service.post_journal_entry(db_session, je.id, co.id, maker.id)
    req_id = exc_info.value.approval_request_id

    with pytest.raises(BusinessRuleViolation, match="requester cannot approve"):
        service.decide_approval(db_session, req_id, True, co.id, maker.id)


# ===========================================================================
# Reversal
# ===========================================================================


def test_reverse_je(db_session):
    ctx = _ctx(db_session, "REV1")
    co = ctx["company"]
    accts = ctx["accts"]
    maker = ctx["maker"]
    _je(db_session, co.id, accts, actor_id=maker.id)  # post first JE

    je = service.create_journal_entry(
        db_session,
        schemas.JournalEntryCreate(
            entry_date=datetime.date(2026, 2, 1),
            lines=[
                schemas.JournalEntryLineCreate(
                    account_id=accts["4100"].id, credit=Decimal("3000")
                ),
                schemas.JournalEntryLineCreate(
                    account_id=accts["1200"].id, debit=Decimal("3000")
                ),
            ],
        ),
        co.id, maker.id,
    )
    service.post_journal_entry(db_session, je.id, co.id, maker.id)

    reversal = service.reverse_journal_entry(
        db_session,
        je.id,
        reversal_date=datetime.date(2026, 2, 15),
        company_id=co.id,
        actor_id=maker.id,
    )
    assert reversal.status == JournalEntryStatus.POSTED
    assert reversal.reversed_entry_id == je.id
    assert reversal.entry_type == EntryType.ADJUSTMENT

    # Original should be REVERSED
    original = service.get_journal_entry(db_session, je.id, co.id)
    assert original.status == JournalEntryStatus.REVERSED

    # Lines are exact opposite
    from app.modules.accounting.models import JournalEntryLine
    orig_lines = db_session.query(JournalEntryLine).filter_by(entry_id=je.id).all()
    rev_lines = db_session.query(JournalEntryLine).filter_by(entry_id=reversal.id).all()
    orig_by_acct = {ln.account_id: (ln.debit, ln.credit) for ln in orig_lines}
    for rln in rev_lines:
        od, oc = orig_by_acct[rln.account_id]
        assert rln.debit == oc   # original credit becomes reversal debit
        assert rln.credit == od  # original debit becomes reversal credit


def test_reverse_already_reversed_rejected(db_session):
    ctx = _ctx(db_session, "REV2")
    co = ctx["company"]
    accts = ctx["accts"]
    maker = ctx["maker"]

    je = service.create_journal_entry(
        db_session,
        schemas.JournalEntryCreate(
            entry_date=datetime.date(2026, 1, 15),
            lines=[
                schemas.JournalEntryLineCreate(
                    account_id=accts["1100"].id, debit=Decimal("100")
                ),
                schemas.JournalEntryLineCreate(
                    account_id=accts["3100"].id, credit=Decimal("100")
                ),
            ],
        ),
        co.id, maker.id,
    )
    service.post_journal_entry(db_session, je.id, co.id, maker.id)
    service.reverse_journal_entry(
        db_session, je.id, datetime.date(2026, 2, 1), co.id, maker.id
    )
    with pytest.raises(BusinessRuleViolation, match="already been reversed"):
        service.reverse_journal_entry(
            db_session, je.id, datetime.date(2026, 3, 1), co.id, maker.id
        )


def test_reverse_draft_je_rejected(db_session):
    ctx = _ctx(db_session, "REVDRAFT")
    co = ctx["company"]
    accts = ctx["accts"]
    je = service.create_journal_entry(
        db_session,
        schemas.JournalEntryCreate(
            entry_date=datetime.date(2026, 1, 15),
            lines=[
                schemas.JournalEntryLineCreate(
                    account_id=accts["1100"].id, debit=Decimal("100")
                ),
                schemas.JournalEntryLineCreate(
                    account_id=accts["3100"].id, credit=Decimal("100")
                ),
            ],
        ),
        co.id, None,
    )
    with pytest.raises(BusinessRuleViolation, match="Only POSTED"):
        service.reverse_journal_entry(
            db_session, je.id, datetime.date(2026, 2, 1), co.id, None
        )


# ===========================================================================
# Reports
# ===========================================================================


def _seed_sham_land_entries(db, ctx):
    """
    Five balanced journal entries that prove the Balance Sheet:
      Assets = 78,650 KWD
      Liabilities (Bank Loan) = 3,150
      Equity (Share Capital) = 75,000
      Net Income = 5,000 - 3,000 - 1,500 = 500
      Total = 78,650 ✓
    Trial Balance debits = credits = 87,650 ✓
    """
    co = ctx["company"]
    accts = ctx["accts"]
    maker = ctx["maker"]
    cid = co.id
    mid = maker.id

    def post(date, lines):
        je = service.create_journal_entry(
            db,
            schemas.JournalEntryCreate(entry_date=date, lines=lines),
            cid, mid,
        )
        service.post_journal_entry(db, je.id, cid, mid)
        return je

    # JE-001: Capital 75,000
    post(datetime.date(2026, 1, 1), [
        schemas.JournalEntryLineCreate(account_id=accts["1100"].id, debit=Decimal("75000")),
        schemas.JournalEntryLineCreate(account_id=accts["3100"].id, credit=Decimal("75000")),
    ])
    # JE-002: Equipment on loan 3,150
    post(datetime.date(2026, 1, 15), [
        schemas.JournalEntryLineCreate(account_id=accts["1300"].id, debit=Decimal("3150")),
        schemas.JournalEntryLineCreate(account_id=accts["2200"].id, credit=Decimal("3150")),
    ])
    # JE-003: Revenue 5,000
    post(datetime.date(2026, 2, 1), [
        schemas.JournalEntryLineCreate(account_id=accts["1200"].id, debit=Decimal("5000")),
        schemas.JournalEntryLineCreate(account_id=accts["4100"].id, credit=Decimal("5000")),
    ])
    # JE-004: COGS 3,000
    post(datetime.date(2026, 2, 1), [
        schemas.JournalEntryLineCreate(account_id=accts["5100"].id, debit=Decimal("3000")),
        schemas.JournalEntryLineCreate(account_id=accts["1100"].id, credit=Decimal("3000")),
    ])
    # JE-005: Salaries 1,500
    post(datetime.date(2026, 2, 28), [
        schemas.JournalEntryLineCreate(account_id=accts["6100"].id, debit=Decimal("1500")),
        schemas.JournalEntryLineCreate(account_id=accts["1100"].id, credit=Decimal("1500")),
    ])


def test_trial_balance_is_balanced(db_session):
    ctx = _ctx(db_session, "TB1")
    _seed_sham_land_entries(db_session, ctx)
    tb = service.get_trial_balance(
        db_session, ctx["company"].id, datetime.date(2026, 12, 31)
    )
    assert tb.is_balanced, (
        f"Trial Balance not balanced: debits={tb.grand_total_debit} "
        f"credits={tb.grand_total_credit}"
    )
    assert tb.grand_total_debit == Decimal("87650")
    assert tb.grand_total_credit == Decimal("87650")


def test_pl_net_income(db_session):
    ctx = _ctx(db_session, "PL1")
    _seed_sham_land_entries(db_session, ctx)
    pl = service.get_pl(
        db_session,
        ctx["company"].id,
        datetime.date(2026, 1, 1),
        datetime.date(2026, 12, 31),
    )
    assert pl.total_revenue == Decimal("5000")
    assert pl.total_expenses == Decimal("4500")
    assert pl.net_income == Decimal("500")


def test_balance_sheet_balances(db_session):
    ctx = _ctx(db_session, "BS1")
    _seed_sham_land_entries(db_session, ctx)
    bs = service.get_balance_sheet(
        db_session, ctx["company"].id, datetime.date(2026, 12, 31)
    )

    assert bs.total_assets == Decimal("78650"), (
        f"Expected assets 78,650 got {bs.total_assets}"
    )
    assert bs.total_liabilities == Decimal("3150")
    assert bs.total_equity_paid_in == Decimal("75000")
    assert bs.retained_earnings == Decimal("500")
    assert bs.total_equity == Decimal("75500")
    assert bs.is_balanced, (
        f"Balance Sheet not balanced: assets={bs.total_assets} "
        f"L+E={bs.total_liabilities + bs.total_equity}"
    )


def test_balance_sheet_asset_breakdown(db_session):
    ctx = _ctx(db_session, "BSBREAK")
    _seed_sham_land_entries(db_session, ctx)
    bs = service.get_balance_sheet(
        db_session, ctx["company"].id, datetime.date(2026, 12, 31)
    )
    asset_map = {a.account_code: a.balance for a in bs.assets}
    # 1100 Bank: 75,000 - 3,000 - 1,500 = 70,500
    assert asset_map["1100"] == Decimal("70500")
    # 1200 AR: 5,000
    assert asset_map["1200"] == Decimal("5000")
    # 1300 Equipment: 3,150
    assert asset_map["1300"] == Decimal("3150")


def test_gl_report(db_session):
    ctx = _ctx(db_session, "GL1")
    _seed_sham_land_entries(db_session, ctx)
    co = ctx["company"]
    accts = ctx["accts"]

    gl = service.get_gl(
        db_session,
        accts["1100"].id,
        co.id,
        datetime.date(2026, 1, 1),
        datetime.date(2026, 12, 31),
    )
    assert gl.account_code == "1100"
    assert gl.closing_balance == Decimal("70500")
    # Three movements: Dr 75000, Cr 3000, Cr 1500
    assert len(gl.entries) == 3


def test_pl_respects_date_range(db_session):
    ctx = _ctx(db_session, "PLRANGE")
    _seed_sham_land_entries(db_session, ctx)
    # P&L for January only — no revenue/expense entries in Jan
    pl = service.get_pl(
        db_session,
        ctx["company"].id,
        datetime.date(2026, 1, 1),
        datetime.date(2026, 1, 31),
    )
    assert pl.total_revenue == Decimal("0")
    assert pl.total_expenses == Decimal("0")
    assert pl.net_income == Decimal("0")


# ===========================================================================
# Posting Template resolution (global vs. company-specific)
# ===========================================================================


def test_posting_template_global_resolution(db_session):
    from app.modules.accounting.models import (
        AccountingPeriod,
        PostingTemplateHeader,
        PostingTemplateLine,
        AccountSelectorType,
    )
    ctx = _ctx(db_session, "PTGLOBAL")
    co = ctx["company"]
    accts = ctx["accts"]
    date = datetime.date(2026, 1, 15)

    # Create a global template (company_id=NULL)
    hdr = PostingTemplateHeader(
        company_id=None,
        event_type="TEST_EVENT",
        version=1,
        effective_from=datetime.date(2026, 1, 1),
    )
    db_session.add(hdr)
    db_session.flush()
    db_session.add(PostingTemplateLine(
        header_id=hdr.id, sequence=1,
        selector_type=AccountSelectorType.FIXED_CODE,
        selector_param="1100", side="DEBIT", amount_source="amount",
    ))
    db_session.add(PostingTemplateLine(
        header_id=hdr.id, sequence=2,
        selector_type=AccountSelectorType.FIXED_CODE,
        selector_param="3100", side="CREDIT", amount_source="amount",
    ))
    db_session.flush()

    result = service._resolve_template(db_session, co.id, "TEST_EVENT", date)
    assert result is not None
    assert result.id == hdr.id


def test_posting_template_company_override(db_session):
    from app.modules.accounting.models import (
        PostingTemplateHeader,
        PostingTemplateLine,
        AccountSelectorType,
    )
    ctx = _ctx(db_session, "PTOVER")
    co = ctx["company"]
    date = datetime.date(2026, 1, 15)

    # Global
    global_hdr = PostingTemplateHeader(
        company_id=None, event_type="OVERRIDE_EVENT", version=1,
        effective_from=datetime.date(2026, 1, 1),
    )
    db_session.add(global_hdr)
    # Company-specific override
    co_hdr = PostingTemplateHeader(
        company_id=co.id, event_type="OVERRIDE_EVENT", version=1,
        effective_from=datetime.date(2026, 1, 1),
    )
    db_session.add(co_hdr)
    db_session.flush()

    result = service._resolve_template(db_session, co.id, "OVERRIDE_EVENT", date)
    assert result.id == co_hdr.id  # company-specific wins


# ===========================================================================
# Posting Engine end-to-end
# ===========================================================================


def test_posting_engine_posts_balanced_entry(db_session):
    from app.modules.accounting.models import (
        PostingTemplateHeader,
        PostingTemplateLine,
        AccountSelectorType,
    )
    from app.modules.accounting.service import PostingEvent, posting_service

    ctx = _ctx(db_session, "ENGINE1")
    co = ctx["company"]
    accts = ctx["accts"]

    hdr = PostingTemplateHeader(
        company_id=None, event_type="ENGINE_TEST", version=1,
        effective_from=datetime.date(2026, 1, 1),
    )
    db_session.add(hdr)
    db_session.flush()
    db_session.add(PostingTemplateLine(
        header_id=hdr.id, sequence=1,
        selector_type=AccountSelectorType.FIXED_CODE,
        selector_param="1100", side="DEBIT", amount_source="amount",
    ))
    db_session.add(PostingTemplateLine(
        header_id=hdr.id, sequence=2,
        selector_type=AccountSelectorType.FIXED_CODE,
        selector_param="4100", side="CREDIT", amount_source="amount",
    ))
    db_session.flush()

    event = PostingEvent(
        event_type="ENGINE_TEST",
        payload={"amount": "2500"},
        entry_date=datetime.date(2026, 1, 15),
        company_id=co.id,
        actor_id=ctx["maker"].id,
        idempotency_key="engine-test-001",
    )
    result = posting_service.post(db_session, event)
    assert result.journal_entry_id is not None
    assert not result.was_idempotent


def test_posting_engine_idempotency(db_session):
    from app.modules.accounting.models import (
        PostingTemplateHeader,
        PostingTemplateLine,
        AccountSelectorType,
    )
    from app.modules.accounting.service import PostingEvent, posting_service

    ctx = _ctx(db_session, "ENGINEM2")
    co = ctx["company"]

    hdr = PostingTemplateHeader(
        company_id=None, event_type="IDEM_ENGINE", version=1,
        effective_from=datetime.date(2026, 1, 1),
    )
    db_session.add(hdr)
    db_session.flush()
    db_session.add(PostingTemplateLine(
        header_id=hdr.id, sequence=1,
        selector_type=AccountSelectorType.FIXED_CODE,
        selector_param="1100", side="DEBIT", amount_source="amount",
    ))
    db_session.add(PostingTemplateLine(
        header_id=hdr.id, sequence=2,
        selector_type=AccountSelectorType.FIXED_CODE,
        selector_param="3100", side="CREDIT", amount_source="amount",
    ))
    db_session.flush()

    event = PostingEvent(
        event_type="IDEM_ENGINE",
        payload={"amount": "100"},
        entry_date=datetime.date(2026, 1, 15),
        company_id=co.id,
        actor_id=None,
        idempotency_key="idem-engine-unique",
    )
    r1 = posting_service.post(db_session, event)
    r2 = posting_service.post(db_session, event)
    assert r2.was_idempotent
    assert r1.journal_entry_id == r2.journal_entry_id


# ===========================================================================
# Engine isolation contract
# ===========================================================================


def test_posting_engine_isolation():
    """PostingService must not import from sales, purchasing, or inventory."""
    service_path = (
        Path(__file__).parent.parent
        / "app" / "modules" / "accounting" / "service.py"
    )
    source = service_path.read_text()
    tree = ast.parse(source)

    forbidden_prefixes = (
        "app.modules.sales",
        "app.modules.purchasing",
        "app.modules.inventory",
    )

    violations = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom) and node.module:
                module = node.module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name
                    for prefix in forbidden_prefixes:
                        if module.startswith(prefix):
                            violations.append(module)
                continue
            else:
                continue
            for prefix in forbidden_prefixes:
                if module.startswith(prefix):
                    violations.append(module)

    assert not violations, (
        f"PostingService imports from business modules (violates isolation): {violations}"
    )
