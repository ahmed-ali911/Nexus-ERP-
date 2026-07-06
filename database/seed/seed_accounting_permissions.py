#!/usr/bin/env python3
"""Seed accounting permission codes into the permissions table.

Run inside the backend container:
    uv run --project /app python /database/seed/seed_accounting_permissions.py
"""

import sys

sys.path.insert(0, "/app")

from app.core.database import SessionLocal
from app.modules.auth.models import Permission

ACCOUNTING_PERMISSIONS = [
    # (code, name_en, name_ar, module)
    # Settings
    ("accounting.settings.view",   "View Accounting Settings",       "عرض إعدادات المحاسبة",       "accounting"),
    ("accounting.settings.update", "Update Accounting Settings",     "تعديل إعدادات المحاسبة",     "accounting"),
    # Accounts
    ("accounting.accounts.view",   "View Chart of Accounts",         "عرض دليل الحسابات",           "accounting"),
    ("accounting.accounts.manage", "Manage Chart of Accounts",       "إدارة دليل الحسابات",         "accounting"),
    # Cost Centers
    ("accounting.cost_centers.view",   "View Cost Centers",          "عرض مراكز التكلفة",           "accounting"),
    ("accounting.cost_centers.manage", "Manage Cost Centers",        "إدارة مراكز التكلفة",         "accounting"),
    # Fiscal Years
    ("accounting.fiscal_years.view",   "View Fiscal Years",          "عرض السنوات المالية",          "accounting"),
    ("accounting.fiscal_years.manage", "Manage Fiscal Years",        "إدارة السنوات المالية",        "accounting"),
    # Accounting Periods
    ("accounting.periods.view",    "View Accounting Periods",        "عرض الفترات المحاسبية",        "accounting"),
    ("accounting.periods.manage",  "Manage Accounting Periods",      "إدارة الفترات المحاسبية",      "accounting"),
    # Posting Templates
    ("accounting.posting_templates.view",   "View Posting Templates", "عرض قوالب الترحيل",          "accounting"),
    ("accounting.posting_templates.manage", "Manage Posting Templates","إدارة قوالب الترحيل",        "accounting"),
    # Journal Entries
    ("accounting.journal_entries.view",    "View Journal Entries",   "عرض قيود اليومية",             "accounting"),
    ("accounting.journal_entries.create",  "Create Journal Entries", "إنشاء قيود اليومية",           "accounting"),
    ("accounting.journal_entries.post",    "Post Journal Entries",   "ترحيل قيود اليومية",           "accounting"),
    ("accounting.journal_entries.reverse", "Reverse Journal Entries","عكس قيود اليومية",             "accounting"),
    # Approvals
    ("accounting.approval.decide", "Decide Accounting Approvals",    "البت في طلبات الاعتماد للمحاسبة","accounting"),
    # Reports
    ("accounting.reports.view",    "View Accounting Reports",        "عرض التقارير المحاسبية",       "accounting"),
]


def main() -> None:
    db = SessionLocal()
    try:
        created = 0
        for code, name_en, name_ar, module in ACCOUNTING_PERMISSIONS:
            if db.query(Permission).filter_by(code=code).first() is None:
                db.add(Permission(code=code, name_en=name_en, name_ar=name_ar, module=module))
                created += 1
        db.commit()
        print(
            f"Seeded {created} accounting permissions "
            f"({len(ACCOUNTING_PERMISSIONS) - created} already existed)."
        )
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
