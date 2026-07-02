"""Seed the developer-defined permission catalog. Idempotent -- add-only,
never deletes or modifies existing rows (the catalog only grows via code).

Run inside the backend container:
    docker-compose exec backend uv run python /database/seed/seed_permissions.py
"""

from app.core.database import SessionLocal
from app.modules.auth.models import Permission

ORGANIZATION_PERMISSIONS = [
    ("organization.company.create", "Create company", "إنشاء شركة"),
    ("organization.company.read", "View company", "عرض الشركة"),
    ("organization.company.update", "Update company", "تعديل الشركة"),
    ("organization.company.delete", "Delete company", "حذف الشركة"),
    ("organization.company.restore", "Restore company", "استعادة الشركة"),
    ("organization.branch.create", "Create branch", "إنشاء فرع"),
    ("organization.branch.read", "View branch", "عرض الفرع"),
    ("organization.branch.update", "Update branch", "تعديل الفرع"),
    ("organization.branch.delete", "Delete branch", "حذف الفرع"),
    ("organization.branch.restore", "Restore branch", "استعادة الفرع"),
    ("organization.warehouse.create", "Create warehouse", "إنشاء مستودع"),
    ("organization.warehouse.read", "View warehouse", "عرض المستودع"),
    ("organization.warehouse.update", "Update warehouse", "تعديل المستودع"),
    ("organization.warehouse.delete", "Delete warehouse", "حذف المستودع"),
    ("organization.warehouse.restore", "Restore warehouse", "استعادة المستودع"),
]


def run() -> None:
    db = SessionLocal()
    try:
        existing_codes = {p.code for p in db.query(Permission).all()}
        created = 0
        for code, name_en, name_ar in ORGANIZATION_PERMISSIONS:
            if code in existing_codes:
                continue
            module = code.split(".")[0]
            db.add(Permission(code=code, name_en=name_en, name_ar=name_ar, module=module))
            created += 1
        db.commit()
        print(f"Seeded {created} new permission(s); {len(existing_codes)} already existed.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
