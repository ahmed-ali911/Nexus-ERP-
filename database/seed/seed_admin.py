"""Seed the System Administrator role (all permissions) and one admin user
for Sham Land, so there's a way to log in. Idempotent.

Depends on seed_organization.py and seed_permissions.py having run first.

Run inside the backend container:
    docker-compose exec backend uv run python /database/seed/seed_admin.py
"""

from app.core.database import SessionLocal
from app.modules.auth import schemas, service
from app.modules.auth.models import Permission, Role, User
from app.modules.organization.models import Company

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "ChangeMe123!"


def run() -> None:
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.code == "SL").first()
        if company is None:
            print("Company 'SL' not found -- run seed_organization.py first.")
            return

        role = db.query(Role).filter(Role.company_id == company.id, Role.code == "SYS_ADMIN").first()
        if role is None:
            role = Role(
                company_id=company.id,
                code="SYS_ADMIN",
                name_en="System Administrator",
                name_ar="مدير النظام",
                is_system=True,
            )
            db.add(role)
            db.flush()
            print(f"Created role: {role.code} (id={role.id})")
        else:
            print(f"Role 'SYS_ADMIN' already exists (id={role.id})")

        all_permissions = db.query(Permission).all()
        role.permissions = all_permissions
        db.flush()
        print(f"Attached {len(all_permissions)} permission(s) to {role.code}")

        user = db.query(User).filter(User.company_id == company.id, User.username == ADMIN_USERNAME).first()
        if user is None:
            user = service.create_user(
                db,
                schemas.UserCreate(
                    username=ADMIN_USERNAME,
                    email="admin@shamland.example",
                    full_name_en="System Administrator",
                    full_name_ar="مدير النظام",
                    password=ADMIN_PASSWORD,
                    is_superuser=True,
                ),
                company_id=company.id,
            )
            print(f"Created user: {user.username} (id={user.id})")
        else:
            print(f"User '{ADMIN_USERNAME}' already exists (id={user.id})")

        service.assign_role_to_user(db, user.id, role.id)
        db.commit()
        print("Seed complete.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
