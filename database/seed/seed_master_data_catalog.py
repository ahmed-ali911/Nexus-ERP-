"""Seed the developer-defined permission catalog for the Master Data module.
Idempotent -- add-only, never deletes or modifies existing rows.

Run inside the backend container:
    docker-compose exec backend uv run python /database/seed/seed_master_data_catalog.py

After running this, re-run seed_admin.py so the System Administrator role
picks up the new permissions (it re-attaches *all* permission rows on every
run, so nothing needs to change there).
"""

from app.core.database import SessionLocal
from app.modules.auth.models import Permission

_ENTITIES = {
    "unit": ("Unit", "وحدة قياس"),
    "category": ("Category", "تصنيف"),
    "product": ("Product", "منتج"),
    "conversion": ("Unit conversion", "تحويل وحدة"),
    "customer": ("Customer", "عميل"),
    "supplier": ("Supplier", "مورد"),
}
_ACTIONS = {
    "create": ("Create", "إنشاء"),
    "read": ("View", "عرض"),
    "update": ("Update", "تعديل"),
    "delete": ("Delete", "حذف"),
    "restore": ("Restore", "استعادة"),
}

MASTER_DATA_PERMISSIONS = [
    (
        f"master_data.{entity}.{action}",
        f"{action_en} {entity_en.lower()}",
        f"{action_ar} {entity_ar}",
    )
    for entity, (entity_en, entity_ar) in _ENTITIES.items()
    for action, (action_en, action_ar) in _ACTIONS.items()
]


def run() -> None:
    db = SessionLocal()
    try:
        existing_codes = {p.code for p in db.query(Permission).all()}
        created = 0
        for code, name_en, name_ar in MASTER_DATA_PERMISSIONS:
            if code in existing_codes:
                continue
            db.add(Permission(code=code, name_en=name_en, name_ar=name_ar, module="master_data"))
            created += 1
        db.commit()
        print(f"Seeded {created} new permission(s); {len(existing_codes)} already existed.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
