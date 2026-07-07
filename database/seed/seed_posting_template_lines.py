#!/usr/bin/env python3
"""Wire the global posting templates with PAYLOAD_ACCOUNT_CODE lines and enable
auto-posting for Sham Land with DISTRIBUTION chart-of-accounts defaults.

Run inside the backend container (after 0008 migration and seed_sham_land_accounting):
    uv run --project /app python /database/seed/seed_posting_template_lines.py

Idempotent: re-running skips templates that already have lines; skips setting
defaults if already configured.
"""
import sys

sys.path.insert(0, "/app")

from app.modules.auth import models as _auth  # noqa: F401
from app.modules.inventory import models as _inv  # noqa: F401
from app.modules.master_data import models as _md  # noqa: F401
from app.modules.organization import models as _org  # noqa: F401
from app.modules.purchasing import models as _pur  # noqa: F401
from app.modules.sales import models as _sal  # noqa: F401
from app.modules.shared import models as _sh  # noqa: F401
from app.modules.accounting import models as _acc  # noqa: F401

from app.core.database import SessionLocal
from app.modules.accounting.models import (
    AccountSelectorType,
    AccountingSettings,
    PostingTemplateHeader,
    PostingTemplateLine,
)
from app.modules.organization.models import Company

COMPANY_CODE = "SL"

# ---------------------------------------------------------------------------
# Template line definitions
# Each tuple: (selector_type, selector_param, side, amount_source, sequence)
# selector_type = PAYLOAD_ACCOUNT_CODE → param is the payload key holding the code
# ---------------------------------------------------------------------------

TEMPLATE_LINES: dict[str, list[tuple]] = {
    # DR receivable (or cash), CR revenue, CR tax (skipped when tax=0)
    "SALES_INVOICE_POSTED": [
        (AccountSelectorType.PAYLOAD_ACCOUNT_CODE, "ar_account",      "DEBIT",  "gross_amount", 10),
        (AccountSelectorType.PAYLOAD_ACCOUNT_CODE, "revenue_account", "CREDIT", "net_amount",   20),
        (AccountSelectorType.PAYLOAD_ACCOUNT_CODE, "tax_account",     "CREDIT", "tax_amount",   30),
    ],
    # DR COGS, CR Inventory — separate event, same transaction
    "SALES_INVOICE_COGS": [
        (AccountSelectorType.PAYLOAD_ACCOUNT_CODE, "cogs_account",      "DEBIT",  "cogs_total", 10),
        (AccountSelectorType.PAYLOAD_ACCOUNT_CODE, "inventory_account", "CREDIT", "cogs_total", 20),
    ],
    # DR cash, CR AR
    "COLLECTION_POSTED": [
        (AccountSelectorType.PAYLOAD_ACCOUNT_CODE, "cash_account", "DEBIT",  "total_amount", 10),
        (AccountSelectorType.PAYLOAD_ACCOUNT_CODE, "ar_account",   "CREDIT", "total_amount", 20),
    ],
    # DR revenue, DR tax (skipped when 0), CR AR  — reverse of sale
    "SALES_CREDIT_NOTE_POSTED": [
        (AccountSelectorType.PAYLOAD_ACCOUNT_CODE, "revenue_account", "DEBIT",  "net_amount",   10),
        (AccountSelectorType.PAYLOAD_ACCOUNT_CODE, "tax_account",     "DEBIT",  "tax_amount",   20),
        (AccountSelectorType.PAYLOAD_ACCOUNT_CODE, "ar_account",      "CREDIT", "gross_amount", 30),
    ],
    # DR Inventory, CR COGS  — stock returned at original cost
    "SALES_CREDIT_NOTE_COGS": [
        (AccountSelectorType.PAYLOAD_ACCOUNT_CODE, "inventory_account", "DEBIT",  "return_cost", 10),
        (AccountSelectorType.PAYLOAD_ACCOUNT_CODE, "cogs_account",      "CREDIT", "return_cost", 20),
    ],
    # DR Inventory, CR GRN Accrual (goods received not yet invoiced)
    "PURCHASE_GRN_POSTED": [
        (AccountSelectorType.PAYLOAD_ACCOUNT_CODE, "inventory_account",   "DEBIT",  "receipt_cost", 10),
        (AccountSelectorType.PAYLOAD_ACCOUNT_CODE, "grn_accrual_account", "CREDIT", "receipt_cost", 20),
    ],
    # DR GRN Accrual (clears receipt accrual), CR AP
    "SUPPLIER_INVOICE_POSTED": [
        (AccountSelectorType.PAYLOAD_ACCOUNT_CODE, "grn_accrual_account", "DEBIT",  "total_amount", 10),
        (AccountSelectorType.PAYLOAD_ACCOUNT_CODE, "ap_account",          "CREDIT", "total_amount", 20),
    ],
    # DR AP, CR Cash
    "SUPPLIER_PAYMENT_POSTED": [
        (AccountSelectorType.PAYLOAD_ACCOUNT_CODE, "ap_account",   "DEBIT",  "total_amount", 10),
        (AccountSelectorType.PAYLOAD_ACCOUNT_CODE, "cash_account", "CREDIT", "total_amount", 20),
    ],
    # DR GRN Accrual, CR Inventory (at current weighted-avg cost)
    "PURCHASE_RETURN_POSTED": [
        (AccountSelectorType.PAYLOAD_ACCOUNT_CODE, "grn_accrual_account", "DEBIT",  "return_cost", 10),
        (AccountSelectorType.PAYLOAD_ACCOUNT_CODE, "inventory_account",   "CREDIT", "return_cost", 20),
    ],
    # DR Inventory, CR Adjustment expense
    "INVENTORY_ADJUSTMENT_IN": [
        (AccountSelectorType.PAYLOAD_ACCOUNT_CODE, "inventory_account",  "DEBIT",  "adjustment_cost", 10),
        (AccountSelectorType.PAYLOAD_ACCOUNT_CODE, "adjustment_account", "CREDIT", "adjustment_cost", 20),
    ],
    # DR Adjustment expense, CR Inventory
    "INVENTORY_ADJUSTMENT_OUT": [
        (AccountSelectorType.PAYLOAD_ACCOUNT_CODE, "adjustment_account", "DEBIT",  "adjustment_cost", 10),
        (AccountSelectorType.PAYLOAD_ACCOUNT_CODE, "inventory_account",  "CREDIT", "adjustment_cost", 20),
    ],
}

# Sham Land default accounts (DISTRIBUTION CoA codes)
SHAM_DEFAULTS = {
    "default_ar_account_code":                    "1130",  # Accounts Receivable
    "default_cash_account_code":                  "1120",  # Bank Account - Main
    "default_sales_revenue_account_code":         "4010",  # Sales Revenue - Products
    "default_tax_payable_account_code":           "2130",  # VAT Payable
    "default_inventory_account_code":             "1150",  # Inventory - Goods
    "default_cogs_account_code":                  "5010",  # Cost of Goods Sold
    "default_ap_account_code":                    "2110",  # Accounts Payable
    "default_grn_accrual_account_code":           "2120",  # Accrued Expenses (GRNI)
    "default_inventory_adjustment_account_code":  "6060",  # Other Operating Expenses
    "default_purchase_variance_account_code":     "6060",  # Other Operating Expenses
}


def _wire_templates(db) -> None:
    """Replace global template lines with PAYLOAD_ACCOUNT_CODE variants.
    Creates missing headers for new event types.
    """
    import datetime
    wired = 0
    skipped = 0

    for event_type, line_defs in TEMPLATE_LINES.items():
        # Find or create the global header
        hdr = (
            db.query(PostingTemplateHeader)
            .filter_by(company_id=None, event_type=event_type, is_deleted=False)
            .first()
        )
        if hdr is None:
            hdr = PostingTemplateHeader(
                company_id=None,
                event_type=event_type,
                version=1,
                effective_from=datetime.date(2026, 1, 1),
                description=f"Auto-generated: {event_type}",
            )
            db.add(hdr)
            db.flush()

        # Check if lines already exist and are PAYLOAD_ACCOUNT_CODE
        existing = (
            db.query(PostingTemplateLine)
            .filter_by(header_id=hdr.id)
            .all()
        )
        if existing and all(
            ln.selector_type == AccountSelectorType.PAYLOAD_ACCOUNT_CODE
            for ln in existing
        ):
            skipped += 1
            continue

        # Delete stale lines (FIXED_CODE placeholders) and insert proper ones
        for ln in existing:
            db.delete(ln)
        db.flush()

        for sel_type, sel_param, side, amount_src, seq in line_defs:
            db.add(PostingTemplateLine(
                header_id=hdr.id,
                selector_type=sel_type,
                selector_param=sel_param,
                side=side,
                amount_source=amount_src,
                sequence=seq,
            ))
        db.flush()
        wired += 1

    print(
        f"  Posting templates: {wired} wired with PAYLOAD_ACCOUNT_CODE lines, "
        f"{skipped} already correct."
    )


def _set_sham_land_defaults(db, company_id: int) -> None:
    settings = (
        db.query(AccountingSettings)
        .filter_by(company_id=company_id)
        .first()
    )
    if settings is None:
        print("  ERROR: AccountingSettings not found for Sham Land. Run seed_sham_land_accounting first.")
        return

    changed = []
    for attr, code in SHAM_DEFAULTS.items():
        if getattr(settings, attr) is None:
            setattr(settings, attr, code)
            changed.append(attr)

    if not settings.enable_auto_posting:
        settings.enable_auto_posting = True
        changed.append("enable_auto_posting")

    db.flush()
    if changed:
        print(f"  Updated AccountingSettings: {', '.join(changed)}.")
    else:
        print("  AccountingSettings already fully configured — skipped.")


def main() -> None:
    db = SessionLocal()
    try:
        print("Wiring posting template lines ...")
        _wire_templates(db)

        co = db.query(Company).filter_by(code=COMPANY_CODE, is_deleted=False).first()
        if co is None:
            print(f"  WARNING: Company '{COMPANY_CODE}' not found; skipping default-account seed.")
        else:
            print(f"Setting default accounts for '{co.name_en}' (id={co.id}) ...")
            _set_sham_land_defaults(db, co.id)

        db.commit()
        print("Done.")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
