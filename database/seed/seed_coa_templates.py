#!/usr/bin/env python3
"""Seed DISTRIBUTION and GENERIC_TRADING chart-of-accounts templates.

Run inside the backend container:
    uv run --project /app python /database/seed/seed_coa_templates.py
"""

import sys

sys.path.insert(0, "/app")

# Import all model modules so SQLAlchemy metadata is complete before any DB op
from app.modules.auth import models as _auth  # noqa: F401
from app.modules.inventory import models as _inv  # noqa: F401
from app.modules.master_data import models as _md  # noqa: F401
from app.modules.organization import models as _org  # noqa: F401
from app.modules.purchasing import models as _pur  # noqa: F401
from app.modules.sales import models as _sal  # noqa: F401
from app.modules.shared import models as _sh  # noqa: F401
from app.modules.accounting import models as _acc  # noqa: F401

from app.core.database import SessionLocal
from app.modules.accounting.models import CoATemplate, CoATemplateLine

# ---------------------------------------------------------------------------
# DISTRIBUTION template  (~35 accounts)
# Sequence numbers are chosen so parents always come before their children.
# ---------------------------------------------------------------------------

DISTRIBUTION_LINES = [
    # (code, name_en, name_ar, account_type, parent_code, is_postable, seq)
    # ── ASSETS ──────────────────────────────────────────────────────────────
    ("1000", "Assets",                  "الأصول",                   "ASSET",     None,   False, 10),
    ("1100", "Current Assets",          "الأصول المتداولة",          "ASSET",     "1000", False, 20),
    ("1110", "Cash on Hand",            "النقدية في الصندوق",        "ASSET",     "1100", True,  30),
    ("1120", "Bank Account - Main",     "الحساب البنكي الرئيسي",     "ASSET",     "1100", True,  40),
    ("1130", "Accounts Receivable",     "المدينون التجاريون",        "ASSET",     "1100", True,  50),
    ("1140", "Other Receivables",       "مدينون آخرون",              "ASSET",     "1100", True,  60),
    ("1150", "Inventory - Goods",       "المخزون",                   "ASSET",     "1100", True,  70),
    ("1160", "Prepaid Expenses",        "مصروفات مدفوعة مقدماً",     "ASSET",     "1100", True,  80),
    ("1200", "Non-Current Assets",      "الأصول غير المتداولة",      "ASSET",     "1000", False, 90),
    ("1210", "Equipment",               "معدات",                     "ASSET",     "1200", True,  100),
    ("1220", "Vehicles",                "مركبات",                    "ASSET",     "1200", True,  110),
    ("1230", "Furniture & Fixtures",    "أثاث وتجهيزات",             "ASSET",     "1200", True,  120),
    ("1290", "Accumulated Depreciation","مجمع الاستهلاك",            "ASSET",     "1200", True,  130),
    # ── LIABILITIES ─────────────────────────────────────────────────────────
    ("2000", "Liabilities",             "الالتزامات",                "LIABILITY", None,   False, 200),
    ("2100", "Current Liabilities",     "الالتزامات المتداولة",      "LIABILITY", "2000", False, 210),
    ("2110", "Accounts Payable",        "الدائنون التجاريون",        "LIABILITY", "2100", True,  220),
    ("2120", "Accrued Expenses",        "مصروفات مستحقة الدفع",      "LIABILITY", "2100", True,  230),
    ("2130", "VAT Payable",             "ضريبة القيمة المضافة",       "LIABILITY", "2100", True,  240),
    ("2140", "Customer Advances",       "مدفوعات العملاء المقدمة",   "LIABILITY", "2100", True,  250),
    ("2200", "Non-Current Liabilities", "الالتزامات غير المتداولة",  "LIABILITY", "2000", False, 260),
    ("2210", "Long-term Bank Loans",    "قروض بنكية طويلة الأجل",    "LIABILITY", "2200", True,  270),
    ("2220", "Long-term Payables",      "دائنون طويلو الأجل",        "LIABILITY", "2200", True,  280),
    # ── EQUITY ──────────────────────────────────────────────────────────────
    ("3000", "Equity",                  "حقوق الملكية",              "EQUITY",    None,   False, 300),
    ("3010", "Share Capital",           "رأس المال المدفوع",         "EQUITY",    "3000", True,  310),
    ("3020", "Additional Paid-in Cap.", "علاوة إصدار",               "EQUITY",    "3000", True,  320),
    ("3030", "Retained Earnings",       "الأرباح المحتجزة",          "EQUITY",    "3000", True,  330),
    # ── REVENUE ─────────────────────────────────────────────────────────────
    ("4000", "Revenue",                 "الإيرادات",                 "REVENUE",   None,   False, 400),
    ("4010", "Sales Revenue - Products","إيرادات المبيعات",          "REVENUE",   "4000", True,  410),
    ("4020", "Sales Revenue - Services","إيرادات الخدمات",           "REVENUE",   "4000", True,  420),
    ("4030", "Other Income",            "إيرادات أخرى",              "REVENUE",   "4000", True,  430),
    # ── COST OF SALES ────────────────────────────────────────────────────────
    ("5000", "Cost of Sales",           "تكلفة المبيعات",            "EXPENSE",   None,   False, 500),
    ("5010", "Cost of Goods Sold",      "تكلفة البضاعة المباعة",     "EXPENSE",   "5000", True,  510),
    ("5020", "Direct Labor",            "عمالة مباشرة",              "EXPENSE",   "5000", True,  520),
    ("5030", "Freight & Handling",      "شحن ومناولة",               "EXPENSE",   "5000", True,  530),
    # ── OPERATING EXPENSES ───────────────────────────────────────────────────
    ("6000", "Operating Expenses",      "المصروفات التشغيلية",       "EXPENSE",   None,   False, 600),
    ("6010", "Salaries & Wages",        "رواتب وأجور",               "EXPENSE",   "6000", True,  610),
    ("6020", "Rent Expense",            "إيجار",                     "EXPENSE",   "6000", True,  620),
    ("6030", "Utilities",               "مرافق عامة",                "EXPENSE",   "6000", True,  630),
    ("6040", "Marketing & Advertising", "تسويق وإعلان",              "EXPENSE",   "6000", True,  640),
    ("6050", "Depreciation Expense",    "مصروف الاستهلاك",           "EXPENSE",   "6000", True,  650),
    ("6060", "Other Operating Exp.",    "مصروفات تشغيلية أخرى",      "EXPENSE",   "6000", True,  660),
]

# ---------------------------------------------------------------------------
# GENERIC_TRADING template  (simplified, ~18 accounts)
# ---------------------------------------------------------------------------

GENERIC_TRADING_LINES = [
    ("1000", "Assets",               "الأصول",              "ASSET",     None,   False, 10),
    ("1100", "Cash & Bank",          "النقدية والبنك",       "ASSET",     "1000", True,  20),
    ("1200", "Trade Receivables",    "المدينون التجاريون",  "ASSET",     "1000", True,  30),
    ("1300", "Inventory",            "المخزون",             "ASSET",     "1000", True,  40),
    ("1400", "Fixed Assets",         "الأصول الثابتة",      "ASSET",     "1000", True,  50),
    ("2000", "Liabilities",          "الالتزامات",          "LIABILITY", None,   False, 100),
    ("2100", "Trade Payables",       "الدائنون التجاريون",  "LIABILITY", "2000", True,  110),
    ("2200", "Loans Payable",        "قروض مستحقة",         "LIABILITY", "2000", True,  120),
    ("3000", "Equity",               "حقوق الملكية",        "EQUITY",    None,   False, 200),
    ("3100", "Owner's Equity",       "حقوق الملاك",         "EQUITY",    "3000", True,  210),
    ("4000", "Revenue",              "الإيرادات",           "REVENUE",   None,   False, 300),
    ("4100", "Sales",                "المبيعات",            "REVENUE",   "4000", True,  310),
    ("4200", "Other Income",         "إيرادات أخرى",        "REVENUE",   "4000", True,  320),
    ("5000", "Cost of Sales",        "تكلفة المبيعات",      "EXPENSE",   None,   False, 400),
    ("5100", "COGS",                 "تكلفة البضاعة",       "EXPENSE",   "5000", True,  410),
    ("6000", "Expenses",             "المصروفات",           "EXPENSE",   None,   False, 500),
    ("6100", "Salaries",             "رواتب",               "EXPENSE",   "6000", True,  510),
    ("6200", "General & Admin",      "مصروفات عامة وإدارية","EXPENSE",   "6000", True,  520),
]


TEMPLATES = [
    {
        "code": "DISTRIBUTION",
        "name_en": "Distribution Company CoA",
        "name_ar": "دليل حسابات شركة التوزيع",
        "description": "Standard chart of accounts for food/product distribution companies.",
        "lines": DISTRIBUTION_LINES,
    },
    {
        "code": "GENERIC_TRADING",
        "name_en": "Generic Trading CoA",
        "name_ar": "دليل حسابات التجارة العامة",
        "description": "Simplified chart of accounts for general trading companies.",
        "lines": GENERIC_TRADING_LINES,
    },
]


def main() -> None:
    db = SessionLocal()
    try:
        total_new = 0
        for tdef in TEMPLATES:
            tmpl = db.query(CoATemplate).filter_by(code=tdef["code"]).first()
            if tmpl is None:
                tmpl = CoATemplate(
                    code=tdef["code"],
                    name_en=tdef["name_en"],
                    name_ar=tdef["name_ar"],
                    description=tdef["description"],
                )
                db.add(tmpl)
                db.flush()
                for code, name_en, name_ar, acct_type, parent_code, is_postable, seq in tdef["lines"]:
                    db.add(CoATemplateLine(
                        template_id=tmpl.id,
                        code=code,
                        name_en=name_en,
                        name_ar=name_ar,
                        account_type=acct_type,
                        parent_code=parent_code,
                        is_postable=is_postable,
                        sequence=seq,
                    ))
                total_new += 1
                print(f"  Created template '{tdef['code']}' with {len(tdef['lines'])} lines.")
            else:
                print(f"  Template '{tdef['code']}' already exists — skipped.")
        db.commit()
        print(f"Done. {total_new} new template(s) created.")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
