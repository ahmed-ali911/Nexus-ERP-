"""Seed sales permissions into the permissions catalog."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.core.database import SessionLocal
from app.modules.auth.models import Permission

SALES_PERMISSIONS = [
    # code, name_en, name_ar
    ("sales.settings.read", "View sales settings", "عرض إعدادات المبيعات"),
    ("sales.settings.update", "Update sales settings", "تعديل إعدادات المبيعات"),
    ("sales.price_list.create", "Create price list", "إنشاء قائمة أسعار"),
    ("sales.price_list.read", "View price lists", "عرض قوائم الأسعار"),
    ("sales.price_list.update", "Update price list", "تعديل قائمة أسعار"),
    ("sales.price_list.delete", "Delete price list", "حذف قائمة أسعار"),
    ("sales.approval.read", "View approval requests", "عرض طلبات الموافقة"),
    ("sales.approval.approve", "Approve / reject requests", "الموافقة أو الرفض"),
    ("sales.invoice.create", "Create sales invoice", "إنشاء فاتورة مبيعات"),
    ("sales.invoice.read", "View sales invoices", "عرض فواتير المبيعات"),
    ("sales.invoice.post", "Post sales invoice", "ترحيل فاتورة مبيعات"),
    ("sales.invoice.cancel", "Cancel sales invoice", "إلغاء فاتورة مبيعات"),
    ("sales.credit_note.create", "Create credit note", "إنشاء إشعار دائن"),
    ("sales.credit_note.read", "View credit notes", "عرض إشعارات الدائن"),
    ("sales.credit_note.post", "Post credit note", "ترحيل إشعار دائن"),
    ("sales.collection.create", "Create collection", "إنشاء تحصيل"),
    ("sales.collection.read", "View collections", "عرض التحصيلات"),
    ("sales.collection.post", "Post collection", "ترحيل تحصيل"),
    ("sales.collection.cancel", "Cancel collection", "إلغاء تحصيل"),
]


def seed() -> None:
    db = SessionLocal()
    try:
        existing_codes = {p.code for p in db.query(Permission).all()}
        created = 0
        for code, name_en, name_ar in SALES_PERMISSIONS:
            if code in existing_codes:
                print(f"  . {code} (already exists)")
                continue
            db.add(Permission(code=code, name_en=name_en, name_ar=name_ar, module="sales"))
            print(f"  + {code}")
            created += 1
        db.commit()
        print(f"Done: {created} new sales permissions seeded.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
