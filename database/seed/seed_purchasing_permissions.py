#!/usr/bin/env python3
"""Seed purchasing permission codes into the permissions table.

Run inside the backend container:
    uv run --project /app python /database/seed/seed_purchasing_permissions.py
"""

import sys

sys.path.insert(0, "/app")

from app.core.database import SessionLocal
from app.modules.auth.models import Permission

PURCHASING_PERMISSIONS = [
    # (code, name_en, name_ar, module)
    # Purchase Orders
    ("purchasing.po.view", "View Purchase Orders", "عرض أوامر الشراء", "purchasing"),
    ("purchasing.po.create", "Create Purchase Orders", "إنشاء أوامر الشراء", "purchasing"),
    ("purchasing.po.approve", "Approve Purchase Orders", "اعتماد أوامر الشراء", "purchasing"),
    ("purchasing.po.cancel", "Cancel Purchase Orders", "إلغاء أوامر الشراء", "purchasing"),
    # Goods Receipts
    ("purchasing.grn.view", "View Goods Receipts", "عرض إيصالات البضاعة", "purchasing"),
    ("purchasing.grn.create", "Create Goods Receipts", "إنشاء إيصالات البضاعة", "purchasing"),
    ("purchasing.grn.post", "Post Goods Receipts", "ترحيل إيصالات البضاعة", "purchasing"),
    ("purchasing.grn.cancel", "Cancel Goods Receipts", "إلغاء إيصالات البضاعة", "purchasing"),
    # Supplier Invoices (Bills)
    ("purchasing.bill.view", "View Supplier Invoices", "عرض فواتير الموردين", "purchasing"),
    ("purchasing.bill.create", "Create Supplier Invoices", "إنشاء فواتير الموردين", "purchasing"),
    ("purchasing.bill.post", "Post Supplier Invoices", "ترحيل فواتير الموردين", "purchasing"),
    ("purchasing.bill.cancel", "Cancel Supplier Invoices", "إلغاء فواتير الموردين", "purchasing"),
    # Purchase Returns
    ("purchasing.return.view", "View Purchase Returns", "عرض مرتجعات الشراء", "purchasing"),
    ("purchasing.return.create", "Create Purchase Returns", "إنشاء مرتجعات الشراء", "purchasing"),
    ("purchasing.return.post", "Post Purchase Returns", "ترحيل مرتجعات الشراء", "purchasing"),
    # Supplier Payments
    ("purchasing.payment.view", "View Supplier Payments", "عرض مدفوعات الموردين", "purchasing"),
    ("purchasing.payment.create", "Create Supplier Payments", "إنشاء مدفوعات الموردين", "purchasing"),
    ("purchasing.payment.post", "Post Supplier Payments", "ترحيل مدفوعات الموردين", "purchasing"),
    ("purchasing.payment.cancel", "Cancel Supplier Payments", "إلغاء مدفوعات الموردين", "purchasing"),
    # Purchasing Settings
    ("purchasing.settings.view", "View Purchasing Settings", "عرض إعدادات الشراء", "purchasing"),
    ("purchasing.settings.update", "Update Purchasing Settings", "تعديل إعدادات الشراء", "purchasing"),
    # Approval management (purchasing scope)
    ("purchasing.approval.decide", "Decide Purchasing Approvals", "البت في طلبات الاعتماد للشراء", "purchasing"),
]


def main():
    db = SessionLocal()
    try:
        created = 0
        for code, name_en, name_ar, module in PURCHASING_PERMISSIONS:
            existing = db.query(Permission).filter_by(code=code).first()
            if existing is None:
                db.add(Permission(code=code, name_en=name_en, name_ar=name_ar, module=module))
                created += 1
        db.commit()
        print(f"Seeded {created} purchasing permissions ({len(PURCHASING_PERMISSIONS) - created} already existed).")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
