"""Seed inventory permissions into the permissions catalog."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.core.database import SessionLocal
from app.modules.auth.models import Permission

INVENTORY_PERMISSIONS = [
    # code, name_en, name_ar
    ("inventory.settings.read", "View inventory settings", "عرض إعدادات المخزون"),
    ("inventory.settings.update", "Update inventory settings", "تعديل إعدادات المخزون"),
    ("inventory.batch.create", "Create batch/lot", "إنشاء دفعة"),
    ("inventory.batch.read", "View batches", "عرض الدفعات"),
    ("inventory.batch.update", "Update batch", "تعديل دفعة"),
    ("inventory.batch.delete", "Delete batch", "حذف دفعة"),
    (
        "inventory.movement.create",
        "Post stock movement",
        "ترحيل حركة مخزون",
    ),
    ("inventory.movement.read", "View stock movements", "عرض حركات المخزون"),
    ("inventory.movement.reverse", "Reverse a stock movement", "عكس حركة مخزون"),
    ("inventory.balance.read", "View stock balances", "عرض أرصدة المخزون"),
    ("inventory.balance.recompute", "Recompute stock balance", "إعادة احتساب رصيد المخزون"),
]


def seed() -> None:
    db = SessionLocal()
    try:
        existing_codes = {p.code for p in db.query(Permission).all()}
        created = 0
        for code, name_en, name_ar in INVENTORY_PERMISSIONS:
            if code in existing_codes:
                print(f"  . {code} (already exists)")
                continue
            db.add(Permission(code=code, name_en=name_en, name_ar=name_ar, module="inventory"))
            print(f"  + {code}")
            created += 1
        db.commit()
        print(f"Done: {created} new inventory permissions seeded.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
