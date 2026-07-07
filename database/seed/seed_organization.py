"""Seed the 'Sham Land' reference case: 1 company, 3 branches, 2 warehouses.

Idempotent -- skips creation if the company code already exists.

Run inside the backend container:
    docker-compose exec backend uv run python /database/seed/seed_organization.py
"""

from app.core.database import SessionLocal
from app.modules.auth import models as _auth_models  # noqa: F401 — registers users table
from app.modules.organization import schemas, service
from app.modules.organization.models import BranchType, Company, WarehouseType


def run() -> None:
    db = SessionLocal()
    try:
        existing = db.query(Company).filter(Company.code == "SL").first()
        if existing is not None:
            print(f"Company 'SL' already exists (id={existing.id}); skipping seed.")
            return

        company = service.create_company(
            db,
            schemas.CompanyCreate(
                code="SL",
                name_en="Sham Land",
                name_ar="شام لاند",
                commercial_registration_no="CR-000123",
                base_currency="KWD",
                timezone="Asia/Kuwait",
            ),
        )
        print(f"Created company: {company.code} (id={company.id})")

        shuwaikh = service.create_branch(
            db,
            schemas.BranchCreate(
                company_id=company.id,
                code="SHW",
                name_en="Shuwaikh Branch",
                name_ar="فرع الشويخ",
                branch_type=BranchType.RETAIL,
            ),
        )
        farwaniya = service.create_branch(
            db,
            schemas.BranchCreate(
                company_id=company.id,
                code="FRW",
                name_en="Farwaniya Branch",
                name_ar="فرع الفروانية",
                branch_type=BranchType.RETAIL,
            ),
        )
        qurain = service.create_branch(
            db,
            schemas.BranchCreate(
                company_id=company.id,
                code="QRN",
                name_en="Qurain Branch",
                name_ar="فرع القرين",
                branch_type=BranchType.BOTH,
            ),
        )
        for branch in (shuwaikh, farwaniya, qurain):
            print(f"Created branch: {branch.code} (id={branch.id}, type={branch.branch_type.value})")

        raw_material_wh = service.create_warehouse(
            db,
            schemas.WarehouseCreate(
                branch_id=qurain.id,
                code="QRN-RM",
                name_en="Qurain Raw Material Warehouse",
                name_ar="مستودع المواد الخام - القرين",
                warehouse_type=WarehouseType.RAW_MATERIAL,
            ),
        )
        finished_goods_wh = service.create_warehouse(
            db,
            schemas.WarehouseCreate(
                branch_id=qurain.id,
                code="QRN-FG",
                name_en="Qurain Finished Goods Warehouse",
                name_ar="مستودع المنتج التام - القرين",
                warehouse_type=WarehouseType.FINISHED_GOODS,
            ),
        )
        for warehouse in (raw_material_wh, finished_goods_wh):
            print(f"Created warehouse: {warehouse.code} (id={warehouse.id}, type={warehouse.warehouse_type.value})")

        db.commit()
        print("Seed complete.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
