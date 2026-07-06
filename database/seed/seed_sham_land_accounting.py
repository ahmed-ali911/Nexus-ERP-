#!/usr/bin/env python3
"""Seed Sham Land accounting: apply DISTRIBUTION CoA, fiscal year 2026,
12 monthly periods, cost centers, posting templates, and five manual JEs
that produce a balanced Trial Balance and Balance Sheet.

Final numbers:
  Trial Balance  debits = credits = 87,650 KWD
  Assets                           = 78,650 KWD
  Liabilities    (Bank Loan)       =  3,150 KWD
  Equity         (Share Capital)   = 75,000 KWD
  Net Income                       =    500 KWD  (= retained earnings)
  L + E + NI                       = 78,650 KWD  ✓

Run inside the backend container:
    uv run --project /app python /database/seed/seed_sham_land_accounting.py
"""

import datetime
import sys
from decimal import Decimal

sys.path.insert(0, "/app")

# Register all SQLAlchemy metadata before any DB operation
from app.modules.auth import models as _auth  # noqa: F401
from app.modules.inventory import models as _inv  # noqa: F401
from app.modules.master_data import models as _md  # noqa: F401
from app.modules.organization import models as _org  # noqa: F401
from app.modules.purchasing import models as _pur  # noqa: F401
from app.modules.sales import models as _sal  # noqa: F401
from app.modules.shared import models as _sh  # noqa: F401
from app.modules.accounting import models as _acc  # noqa: F401

from app.core.database import SessionLocal
from app.modules.accounting import schemas, service
from app.modules.accounting.models import (
    Account,
    AccountingPeriod,
    AccountingSettings,
    AccountSelectorType,
    CostCenter,
    FiscalYear,
    PostingTemplateHeader,
    PostingTemplateLine,
)
from app.modules.organization.models import Company


COMPANY_CODE = "SL"

# Global posting templates to seed (unwired — ready for future integration)
# Each entry: (event_type, description, [(selector_type, param, side, amount_src), ...])
POSTING_TEMPLATES = [
    (
        "SALES_INVOICE_POSTED",
        "Auto-post when a sales invoice is marked POSTED",
        [
            (AccountSelectorType.FIXED_CODE, "1130", "DEBIT",  "total_amount"),
            (AccountSelectorType.FIXED_CODE, "4010", "CREDIT", "total_amount"),
        ],
    ),
    (
        "SALES_CREDIT_NOTE_POSTED",
        "Auto-post when a sales credit note is POSTED",
        [
            (AccountSelectorType.FIXED_CODE, "4010", "DEBIT",  "total_amount"),
            (AccountSelectorType.FIXED_CODE, "1130", "CREDIT", "total_amount"),
        ],
    ),
    (
        "COLLECTION_POSTED",
        "Auto-post when a customer collection is POSTED",
        [
            (AccountSelectorType.FIXED_CODE, "1120", "DEBIT",  "amount"),
            (AccountSelectorType.FIXED_CODE, "1130", "CREDIT", "amount"),
        ],
    ),
    (
        "PURCHASE_GRN_POSTED",
        "Auto-post when a goods receipt note is POSTED",
        [
            (AccountSelectorType.FIXED_CODE, "1150", "DEBIT",  "total_cost"),
            (AccountSelectorType.FIXED_CODE, "2110", "CREDIT", "total_cost"),
        ],
    ),
    (
        "SUPPLIER_INVOICE_POSTED",
        "Auto-post when a supplier invoice is POSTED",
        [
            (AccountSelectorType.FIXED_CODE, "2110", "DEBIT",  "total_amount"),
            (AccountSelectorType.FIXED_CODE, "2110", "DEBIT",  "total_amount"),  # placeholder
        ],
    ),
    (
        "SUPPLIER_PAYMENT_POSTED",
        "Auto-post when a supplier payment is POSTED",
        [
            (AccountSelectorType.FIXED_CODE, "2110", "DEBIT",  "amount"),
            (AccountSelectorType.FIXED_CODE, "1120", "CREDIT", "amount"),
        ],
    ),
    (
        "PURCHASE_RETURN_POSTED",
        "Auto-post when a purchase return is POSTED",
        [
            (AccountSelectorType.FIXED_CODE, "2110", "DEBIT",  "total_amount"),
            (AccountSelectorType.FIXED_CODE, "1150", "CREDIT", "total_amount"),
        ],
    ),
    (
        "INVENTORY_ADJUSTMENT_IN",
        "Auto-post for positive stock adjustment",
        [
            (AccountSelectorType.FIXED_CODE, "1150", "DEBIT",  "total_cost"),
            (AccountSelectorType.FIXED_CODE, "6060", "CREDIT", "total_cost"),
        ],
    ),
    (
        "INVENTORY_ADJUSTMENT_OUT",
        "Auto-post for negative stock adjustment",
        [
            (AccountSelectorType.FIXED_CODE, "6060", "DEBIT",  "total_cost"),
            (AccountSelectorType.FIXED_CODE, "1150", "CREDIT", "total_cost"),
        ],
    ),
]

COST_CENTERS = [
    ("OPS",   "Operations",   "العمليات"),
    ("SALES", "Sales",        "المبيعات"),
    ("ADMIN", "Administration","الإدارة"),
    ("WH",    "Warehouses",   "المستودعات"),
]


def _get_company(db) -> Company:
    co = db.query(Company).filter_by(code=COMPANY_CODE, is_deleted=False).first()
    if co is None:
        raise RuntimeError(
            f"Company '{COMPANY_CODE}' not found. Run seed_organization.py first."
        )
    return co


def _apply_distribution_coa(db, company_id: int) -> None:
    existing = db.query(Account).filter_by(company_id=company_id, is_deleted=False).first()
    if existing:
        print("  Chart of accounts already applied — skipped.")
        return
    accounts = service.apply_coa_template(db, company_id, "DISTRIBUTION", actor_id=None)
    print(f"  Applied DISTRIBUTION CoA: {len(accounts)} accounts created.")


def _seed_fiscal_year(db, company_id: int) -> FiscalYear:
    fy = db.query(FiscalYear).filter_by(
        company_id=company_id, code="FY2026", is_deleted=False
    ).first()
    if fy:
        print("  Fiscal year FY2026 already exists — skipped.")
        return fy
    fy = service.create_fiscal_year(
        db,
        schemas.FiscalYearCreate(
            code="FY2026",
            name_en="Fiscal Year 2026",
            name_ar="السنة المالية 2026",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31),
        ),
        company_id=company_id,
        actor_id=None,
    )
    print(f"  Created fiscal year FY2026 (id={fy.id}).")
    return fy


def _seed_periods(db, company_id: int, fy_id: int) -> list[AccountingPeriod]:
    existing = (
        db.query(AccountingPeriod)
        .filter_by(company_id=company_id, fiscal_year_id=fy_id)
        .all()
    )
    if existing:
        print(f"  {len(existing)} periods already exist — skipped.")
        return existing
    periods = service.generate_periods(
        db,
        schemas.GeneratePeriodsRequest(fiscal_year_id=fy_id, count=12),
        company_id=company_id,
        actor_id=None,
    )
    print(f"  Created {len(periods)} monthly periods.")
    return periods


def _seed_cost_centers(db, company_id: int) -> None:
    for code, name_en, name_ar in COST_CENTERS:
        exists = db.query(CostCenter).filter_by(
            company_id=company_id, code=code, is_deleted=False
        ).first()
        if exists:
            continue
        service.create_cost_center(
            db,
            schemas.CostCenterCreate(code=code, name_en=name_en, name_ar=name_ar),
            company_id=company_id,
            actor_id=None,
        )
    print(f"  Seeded {len(COST_CENTERS)} cost centers.")


def _seed_posting_templates(db, company_id: int) -> None:
    # Only seed if no global templates exist for these event types
    created = 0
    for event_type, description, line_defs in POSTING_TEMPLATES:
        exists = db.query(PostingTemplateHeader).filter_by(
            company_id=None,
            event_type=event_type,
            is_deleted=False,
        ).first()
        if exists:
            continue
        hdr = PostingTemplateHeader(
            company_id=None,  # global
            event_type=event_type,
            version=1,
            effective_from=datetime.date(2026, 1, 1),
            description=description,
        )
        db.add(hdr)
        db.flush()
        for seq, (stype, sparam, side, amount_src) in enumerate(line_defs, start=1):
            db.add(PostingTemplateLine(
                header_id=hdr.id,
                sequence=seq,
                selector_type=stype,
                selector_param=sparam,
                side=side,
                amount_source=amount_src,
            ))
        db.flush()
        created += 1
    print(f"  Seeded {created} global posting templates ({len(POSTING_TEMPLATES) - created} already existed).")


def _account(db, company_id: int, code: str) -> Account:
    a = db.query(Account).filter_by(
        company_id=company_id, code=code, is_deleted=False
    ).first()
    if a is None:
        raise RuntimeError(
            f"Account '{code}' not found — apply DISTRIBUTION CoA first."
        )
    return a


def _seed_manual_entries(db, company_id: int) -> None:
    settings = service.get_or_create_settings(db, company_id)

    def _already_posted(key: str) -> bool:
        from app.modules.accounting.models import JournalEntry
        return db.query(JournalEntry).filter_by(
            company_id=company_id, idempotency_key=key
        ).first() is not None

    def post(key: str, date: datetime.date, description: str, lines: list) -> None:
        if _already_posted(key):
            print(f"    {key} already posted — skipped.")
            return
        je = service.create_journal_entry(
            db,
            schemas.JournalEntryCreate(
                entry_date=date,
                description=description,
                entry_type="OPENING" if "opening" in key else "STANDARD",
                idempotency_key=key,
                lines=lines,
            ),
            company_id=company_id,
            actor_id=None,
        )
        service.post_journal_entry(db, je.id, company_id, actor_id=None)
        print(f"    Posted {key} ({je.entry_number}).")

    bank  = _account(db, company_id, "1120")
    ar    = _account(db, company_id, "1130")
    equip = _account(db, company_id, "1210")
    loan  = _account(db, company_id, "2210")
    capil = _account(db, company_id, "3010")
    rev   = _account(db, company_id, "4010")
    cogs  = _account(db, company_id, "5010")
    sal   = _account(db, company_id, "6010")

    # JE-001: Initial capital contribution  Dr Bank 75,000 / Cr Share Capital 75,000
    post(
        "SHAM-JE-001-capital",
        datetime.date(2026, 1, 1),
        "Opening balance — share capital contribution",
        [
            schemas.JournalEntryLineCreate(account_id=bank.id,  debit=Decimal("75000")),
            schemas.JournalEntryLineCreate(account_id=capil.id, credit=Decimal("75000")),
        ],
    )

    # JE-002: Equipment purchase on bank loan  Dr Equipment 3,150 / Cr Long-term Loan 3,150
    post(
        "SHAM-JE-002-equipment",
        datetime.date(2026, 1, 15),
        "Equipment purchased — financed by long-term bank loan",
        [
            schemas.JournalEntryLineCreate(account_id=equip.id, debit=Decimal("3150")),
            schemas.JournalEntryLineCreate(account_id=loan.id,  credit=Decimal("3150")),
        ],
    )

    # JE-003: Revenue 5,000  Dr AR / Cr Sales Revenue
    post(
        "SHAM-JE-003-revenue",
        datetime.date(2026, 2, 1),
        "Sales revenue — food products",
        [
            schemas.JournalEntryLineCreate(account_id=ar.id,  debit=Decimal("5000")),
            schemas.JournalEntryLineCreate(account_id=rev.id, credit=Decimal("5000")),
        ],
    )

    # JE-004: COGS 3,000  Dr COGS / Cr Bank (direct purchase for resale)
    post(
        "SHAM-JE-004-cogs",
        datetime.date(2026, 2, 1),
        "Cost of goods sold",
        [
            schemas.JournalEntryLineCreate(account_id=cogs.id, debit=Decimal("3000")),
            schemas.JournalEntryLineCreate(account_id=bank.id, credit=Decimal("3000")),
        ],
    )

    # JE-005: Salaries 1,500  Dr Salaries / Cr Bank
    post(
        "SHAM-JE-005-salaries",
        datetime.date(2026, 2, 28),
        "February salaries",
        [
            schemas.JournalEntryLineCreate(account_id=sal.id,  debit=Decimal("1500")),
            schemas.JournalEntryLineCreate(account_id=bank.id, credit=Decimal("1500")),
        ],
    )


def _print_reports(db, company_id: int) -> None:
    print("\n" + "=" * 60)
    print("  SHAM LAND — Financial Reports (as of 2026-12-31)")
    print("=" * 60)

    as_of = datetime.date(2026, 12, 31)

    # Trial Balance
    tb = service.get_trial_balance(db, company_id, as_of)
    print(f"\n  Trial Balance")
    print(f"  {'Account':<35} {'Debit':>12} {'Credit':>12}")
    print(f"  {'-'*35} {'-'*12} {'-'*12}")
    for ln in tb.lines:
        print(f"  {ln.account_code} {ln.account_name:<30} "
              f"{ln.total_debit:>12,.3f} {ln.total_credit:>12,.3f}")
    print(f"  {'TOTAL':<35} {tb.grand_total_debit:>12,.3f} {tb.grand_total_credit:>12,.3f}")
    print(f"  Balanced: {tb.is_balanced}")

    # P&L
    pl = service.get_pl(db, company_id, datetime.date(2026, 1, 1), as_of)
    print(f"\n  Profit & Loss (Jan – Dec 2026)")
    for ln in pl.revenue_lines:
        print(f"    Revenue  {ln.account_code} {ln.account_name:<28} {ln.net_amount:>12,.3f}")
    for ln in pl.expense_lines:
        print(f"    Expense  {ln.account_code} {ln.account_name:<28} {ln.net_amount:>12,.3f}")
    print(f"  Total Revenue:   {pl.total_revenue:>12,.3f}")
    print(f"  Total Expenses:  {pl.total_expenses:>12,.3f}")
    print(f"  Net Income:      {pl.net_income:>12,.3f}")

    # Balance Sheet
    bs = service.get_balance_sheet(db, company_id, as_of)
    print(f"\n  Balance Sheet (as of {as_of})")
    print(f"  ASSETS:")
    for a in bs.assets:
        print(f"    {a.account_code} {a.account_name:<30} {a.balance:>12,.3f}")
    print(f"  Total Assets:                            {bs.total_assets:>12,.3f}")
    print(f"\n  LIABILITIES:")
    for a in bs.liabilities:
        print(f"    {a.account_code} {a.account_name:<30} {a.balance:>12,.3f}")
    print(f"  Total Liabilities:                       {bs.total_liabilities:>12,.3f}")
    print(f"\n  EQUITY:")
    for a in bs.equity:
        print(f"    {a.account_code} {a.account_name:<30} {a.balance:>12,.3f}")
    print(f"  Retained Earnings (Net Income):          {bs.retained_earnings:>12,.3f}")
    print(f"  Total Equity (paid-in + RE):             {bs.total_equity:>12,.3f}")
    print(f"\n  Total Liabilities + Equity:              "
          f"{bs.total_liabilities + bs.total_equity:>12,.3f}")
    print(f"  Total Assets:                            {bs.total_assets:>12,.3f}")
    print(f"  Balance Sheet BALANCED: {bs.is_balanced}")
    print("=" * 60)


def main() -> None:
    db = SessionLocal()
    try:
        co = _get_company(db)
        print(f"\nSeeding accounting for '{co.name_en}' (id={co.id}) ...")

        _apply_distribution_coa(db, co.id)
        fy = _seed_fiscal_year(db, co.id)
        _seed_periods(db, co.id, fy.id)
        _seed_cost_centers(db, co.id)
        _seed_posting_templates(db, co.id)

        print("\n  Posting manual journal entries ...")
        _seed_manual_entries(db, co.id)

        db.commit()
        print("\nAll committed. Printing reports ...\n")
        _print_reports(db, co.id)

    except Exception as e:
        db.rollback()
        print(f"\nError: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
