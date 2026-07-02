"""Seed inventory for the 'Sham Land' reference case:
  - Mark batch-tracked products
  - Create a retail warehouse on the Shuwaikh branch (transfer destination)
  - Create batches with varied expiry dates (some expiring soon)
  - Post opening RECEIPT movements (weighted-average costs computed live)
  - Post a factory→retail TRANSFER to exercise the transfer leg logic

Idempotent: checks for existing batches/movements before creating.

Depends on seed_organization.py, seed_admin.py, seed_master_data_catalog.py,
seed_inventory_catalog.py, seed_sham_land_master_data.py having run first.

Run inside the backend container:
    docker-compose exec backend uv run python /database/seed/seed_sham_land_inventory.py
"""

import datetime
from decimal import Decimal

from app.core.database import SessionLocal
from app.modules.auth.models import User
from app.modules.inventory import schemas as inv_schemas, service as inv_service
from app.modules.inventory.models import Batch, StockMovement
from app.modules.master_data.models import Product
from app.modules.organization import schemas as org_schemas, service as org_service
from app.modules.organization.models import Branch, BranchType, Company, Warehouse, WarehouseType


def _get_warehouse(db, company_id, code):
    return (
        db.query(Warehouse)
        .join(Branch, Warehouse.branch_id == Branch.id)
        .filter(Branch.company_id == company_id, Warehouse.code == code, Warehouse.is_deleted.is_(False))
        .first()
    )


def _get_branch(db, company_id, code):
    return db.query(Branch).filter(Branch.company_id == company_id, Branch.code == code).first()


def _get_product(db, company_id, code):
    return db.query(Product).filter(Product.company_id == company_id, Product.code == code).first()


def _get_or_create_batch(db, company_id, actor_id, product_id, batch_number, expiry_date, notes=None):
    existing = (
        db.query(Batch)
        .filter(
            Batch.company_id == company_id,
            Batch.product_id == product_id,
            Batch.batch_number == batch_number,
        )
        .first()
    )
    if existing is not None:
        return existing, False
    batch = inv_service.create_batch(
        db,
        inv_schemas.BatchCreate(
            product_id=product_id,
            batch_number=batch_number,
            expiry_date=expiry_date,
            notes=notes,
        ),
        company_id=company_id,
        actor_id=actor_id,
    )
    return batch, True


def _has_movements(db, company_id, warehouse_id, product_id):
    return (
        db.query(StockMovement)
        .filter(
            StockMovement.company_id == company_id,
            StockMovement.warehouse_id == warehouse_id,
            StockMovement.product_id == product_id,
        )
        .first()
        is not None
    )


def run() -> None:
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.code == "SL").first()
        if company is None:
            print("Company 'SL' not found -- run seed_organization.py first.")
            return

        admin = db.query(User).filter(User.company_id == company.id, User.username == "admin").first()
        actor_id = admin.id if admin else None

        # --- Mark products as batch-tracked --------------------------------
        today = datetime.date.today()

        for code in ("GREEN-COFFEE", "ROASTED-COFFEE", "ROASTED-ALMONDS"):
            product = _get_product(db, company.id, code)
            if product is None:
                print(f"  Product {code} not found; skipping.")
                continue
            if not product.is_batch_tracked:
                product.is_batch_tracked = True
                print(f"  Marked {code} as batch-tracked")
            else:
                print(f"  {code} already batch-tracked")

        db.flush()

        # --- Ensure a retail warehouse exists on the Shuwaikh branch -------
        shw_branch = _get_branch(db, company.id, "SHW")
        if shw_branch is None:
            print("Branch 'SHW' not found; run seed_organization.py first.")
            return

        shw_wh = _get_warehouse(db, company.id, "SHW-RETAIL")
        if shw_wh is None:
            shw_wh = org_service.create_warehouse(
                db,
                org_schemas.WarehouseCreate(
                    branch_id=shw_branch.id,
                    code="SHW-RETAIL",
                    name_en="Shuwaikh Retail Warehouse",
                    name_ar="مستودع التجزئة - الشويخ",
                    warehouse_type=WarehouseType.FINISHED_GOODS,
                ),
            )
            print(f"  Created warehouse: {shw_wh.code} (id={shw_wh.id})")
        else:
            print(f"  Warehouse {shw_wh.code} already exists (id={shw_wh.id})")

        # Resolve factory warehouses
        qrn_rm = _get_warehouse(db, company.id, "QRN-RM")
        qrn_fg = _get_warehouse(db, company.id, "QRN-FG")
        if qrn_rm is None or qrn_fg is None:
            print("QRN warehouses not found; run seed_organization.py first.")
            return

        green_coffee = _get_product(db, company.id, "GREEN-COFFEE")
        roasted_coffee = _get_product(db, company.id, "ROASTED-COFFEE")
        roasted_almonds = _get_product(db, company.id, "ROASTED-ALMONDS")
        mixed_nuts_box = _get_product(db, company.id, "MIXED-NUTS-BOX")

        settings = inv_service.get_or_create_settings(db, company.id)

        # --- Create batches ------------------------------------------------
        print("\n--- Batches ---")

        # Green Coffee batches: 2 batches, one expiring soon
        gc_batch_a, created = _get_or_create_batch(
            db, company.id, actor_id, green_coffee.id,
            batch_number="GC-2026-001",
            expiry_date=today + datetime.timedelta(days=180),
            notes="Yemen import - Jan 2026",
        )
        print(f"  {'Created' if created else 'Exists'}: batch {gc_batch_a.batch_number} (expires {gc_batch_a.expiry_date})")

        gc_batch_b, created = _get_or_create_batch(
            db, company.id, actor_id, green_coffee.id,
            batch_number="GC-2026-002",
            expiry_date=today + datetime.timedelta(days=20),  # expiring SOON
            notes="Yemen import - Feb 2026 (low stock, near expiry)",
        )
        print(f"  {'Created' if created else 'Exists'}: batch {gc_batch_b.batch_number} (expires {gc_batch_b.expiry_date}) *** EXPIRING SOON ***")

        # Roasted Coffee batches
        rc_batch_a, created = _get_or_create_batch(
            db, company.id, actor_id, roasted_coffee.id,
            batch_number="RC-2026-001",
            expiry_date=today + datetime.timedelta(days=90),
            notes="Medium roast - production lot A",
        )
        print(f"  {'Created' if created else 'Exists'}: batch {rc_batch_a.batch_number} (expires {rc_batch_a.expiry_date})")

        rc_batch_b, created = _get_or_create_batch(
            db, company.id, actor_id, roasted_coffee.id,
            batch_number="RC-2026-002",
            expiry_date=today + datetime.timedelta(days=25),  # expiring SOON
            notes="Medium roast - production lot B (near expiry)",
        )
        print(f"  {'Created' if created else 'Exists'}: batch {rc_batch_b.batch_number} (expires {rc_batch_b.expiry_date}) *** EXPIRING SOON ***")

        # Roasted Almonds batch
        ra_batch, created = _get_or_create_batch(
            db, company.id, actor_id, roasted_almonds.id,
            batch_number="RA-2026-001",
            expiry_date=today + datetime.timedelta(days=120),
            notes="Roasted almonds - production lot",
        )
        print(f"  {'Created' if created else 'Exists'}: batch {ra_batch.batch_number} (expires {ra_batch.expiry_date})")

        db.flush()

        # --- Opening receipts into QRN-RM (raw materials) ------------------
        print("\n--- Opening receipts: QRN-RM (raw materials) ---")

        if not _has_movements(db, company.id, qrn_rm.id, green_coffee.id):
            # Receipt 1: batch A — 500 kg of green coffee at 2.500 KWD/kg
            # quantity in base unit (grams): 500,000 g
            mv = inv_service.receive_stock(
                db,
                inv_schemas.ReceiveStockRequest(
                    warehouse_id=qrn_rm.id,
                    product_id=green_coffee.id,
                    batch_id=gc_batch_a.id,
                    quantity=Decimal("500000"),  # 500 kg in grams
                    unit_cost=Decimal("0.0025"),   # 2.500 KWD/kg = 0.0025 KWD/g
                    notes="Opening stock - GC-2026-001",
                ),
                company_id=company.id,
                actor_id=actor_id,
            )
            print(f"  Receipt (id={mv.id}): GREEN-COFFEE batch GC-2026-001: 500,000 g @ 0.0025 KWD/g = {mv.total_cost} KWD")

            # Receipt 2: batch B — 100 kg at 2.600 KWD/kg (slightly pricier)
            mv2 = inv_service.receive_stock(
                db,
                inv_schemas.ReceiveStockRequest(
                    warehouse_id=qrn_rm.id,
                    product_id=green_coffee.id,
                    batch_id=gc_batch_b.id,
                    quantity=Decimal("100000"),  # 100 kg in grams
                    unit_cost=Decimal("0.0026"),
                    notes="Opening stock - GC-2026-002 (near expiry)",
                ),
                company_id=company.id,
                actor_id=actor_id,
            )
            print(f"  Receipt (id={mv2.id}): GREEN-COFFEE batch GC-2026-002: 100,000 g @ 0.0026 KWD/g = {mv2.total_cost} KWD")

            # Show resulting balance
            bal_a = inv_service._get_balance(db, company.id, qrn_rm.id, green_coffee.id, gc_batch_a.id)
            bal_b = inv_service._get_balance(db, company.id, qrn_rm.id, green_coffee.id, gc_batch_b.id)
            print(f"  Balance GC batch A: {bal_a.quantity_on_hand} g, WAC={bal_a.weighted_avg_cost}")
            print(f"  Balance GC batch B: {bal_b.quantity_on_hand} g, WAC={bal_b.weighted_avg_cost}")
        else:
            print("  GREEN-COFFEE movements already exist; skipping.")

        # --- Opening receipts into QRN-FG (finished goods) -----------------
        print("\n--- Opening receipts: QRN-FG (finished goods) ---")

        if not _has_movements(db, company.id, qrn_fg.id, roasted_coffee.id):
            # Roasted Coffee batch A: 200 kg at 4.500 KWD/kg = 0.0045 KWD/g
            mv = inv_service.receive_stock(
                db,
                inv_schemas.ReceiveStockRequest(
                    warehouse_id=qrn_fg.id,
                    product_id=roasted_coffee.id,
                    batch_id=rc_batch_a.id,
                    quantity=Decimal("200000"),
                    unit_cost=Decimal("0.0045"),
                    notes="Opening stock - RC-2026-001",
                ),
                company_id=company.id,
                actor_id=actor_id,
            )
            print(f"  Receipt (id={mv.id}): ROASTED-COFFEE batch RC-2026-001: 200,000 g @ 0.0045 = {mv.total_cost} KWD")

            # Roasted Coffee batch B: 80 kg at 4.800 KWD/kg (higher cost run)
            mv2 = inv_service.receive_stock(
                db,
                inv_schemas.ReceiveStockRequest(
                    warehouse_id=qrn_fg.id,
                    product_id=roasted_coffee.id,
                    batch_id=rc_batch_b.id,
                    quantity=Decimal("80000"),
                    unit_cost=Decimal("0.0048"),
                    notes="Opening stock - RC-2026-002",
                ),
                company_id=company.id,
                actor_id=actor_id,
            )
            print(f"  Receipt (id={mv2.id}): ROASTED-COFFEE batch RC-2026-002: 80,000 g @ 0.0048 = {mv2.total_cost} KWD")

            # Show balance
            bal_a = inv_service._get_balance(db, company.id, qrn_fg.id, roasted_coffee.id, rc_batch_a.id)
            bal_b = inv_service._get_balance(db, company.id, qrn_fg.id, roasted_coffee.id, rc_batch_b.id)
            print(f"  Balance RC batch A: {bal_a.quantity_on_hand} g, WAC={bal_a.weighted_avg_cost}")
            print(f"  Balance RC batch B: {bal_b.quantity_on_hand} g, WAC={bal_b.weighted_avg_cost}")
        else:
            print("  ROASTED-COFFEE movements already exist; skipping.")

        if not _has_movements(db, company.id, qrn_fg.id, roasted_almonds.id):
            mv = inv_service.receive_stock(
                db,
                inv_schemas.ReceiveStockRequest(
                    warehouse_id=qrn_fg.id,
                    product_id=roasted_almonds.id,
                    batch_id=ra_batch.id,
                    quantity=Decimal("150000"),  # 150 kg in grams
                    unit_cost=Decimal("0.0080"),  # 8.000 KWD/kg
                    notes="Opening stock - RA-2026-001",
                ),
                company_id=company.id,
                actor_id=actor_id,
            )
            print(f"  Receipt (id={mv.id}): ROASTED-ALMONDS batch RA-2026-001: 150,000 g @ 0.008 = {mv.total_cost} KWD")
            bal = inv_service._get_balance(db, company.id, qrn_fg.id, roasted_almonds.id, ra_batch.id)
            print(f"  Balance RA batch A: {bal.quantity_on_hand} g, WAC={bal.weighted_avg_cost}")
        else:
            print("  ROASTED-ALMONDS movements already exist; skipping.")

        # Mixed Nuts Box (COUNT-based, no batch tracking)
        if not _has_movements(db, company.id, qrn_fg.id, mixed_nuts_box.id):
            mv = inv_service.receive_stock(
                db,
                inv_schemas.ReceiveStockRequest(
                    warehouse_id=qrn_fg.id,
                    product_id=mixed_nuts_box.id,
                    batch_id=None,  # not batch-tracked
                    quantity=Decimal("240"),  # 240 boxes (20 cartons x 12)
                    unit_cost=Decimal("3.500"),   # 3.500 KWD/box
                    notes="Opening stock - 20 cartons",
                ),
                company_id=company.id,
                actor_id=actor_id,
            )
            print(f"  Receipt (id={mv.id}): MIXED-NUTS-BOX: 240 boxes @ 3.500 = {mv.total_cost} KWD")
            bal = inv_service._get_balance(db, company.id, qrn_fg.id, mixed_nuts_box.id, None)
            print(f"  Balance MIXED-NUTS-BOX: {bal.quantity_on_hand} pcs, WAC={bal.weighted_avg_cost}")
        else:
            print("  MIXED-NUTS-BOX movements already exist; skipping.")

        # --- Transfer: QRN-FG → SHW-RETAIL ---------------------------------
        print("\n--- Transfer: QRN-FG → SHW-RETAIL ---")

        already_transferred = (
            db.query(StockMovement)
            .filter(
                StockMovement.company_id == company.id,
                StockMovement.warehouse_id == shw_wh.id,
                StockMovement.product_id == roasted_coffee.id,
            )
            .first()
            is not None
        )
        if not already_transferred:
            # Transfer 30 kg of roasted coffee (batch A) from factory to retail
            out_mv, in_mv = inv_service.transfer_stock(
                db,
                inv_schemas.TransferStockRequest(
                    from_warehouse_id=qrn_fg.id,
                    to_warehouse_id=shw_wh.id,
                    product_id=roasted_coffee.id,
                    batch_id=rc_batch_a.id,
                    quantity=Decimal("30000"),  # 30 kg in grams
                    notes="Retail replenishment - Shuwaikh branch",
                ),
                company_id=company.id,
                actor_id=actor_id,
            )
            print(f"  TRANSFER_OUT (id={out_mv.id}): 30,000 g ROASTED-COFFEE from QRN-FG (linked to IN id={out_mv.reference_id})")
            print(f"  TRANSFER_IN  (id={in_mv.id}): 30,000 g ROASTED-COFFEE into SHW-RETAIL (linked to OUT id={in_mv.reference_id})")

            bal_factory = inv_service._get_balance(db, company.id, qrn_fg.id, roasted_coffee.id, rc_batch_a.id)
            bal_retail = inv_service._get_balance(db, company.id, shw_wh.id, roasted_coffee.id, rc_batch_a.id)
            print(f"  QRN-FG balance (batch A after transfer): {bal_factory.quantity_on_hand} g, WAC={bal_factory.weighted_avg_cost}")
            print(f"  SHW-RETAIL balance (batch A after transfer): {bal_retail.quantity_on_hand} g, WAC={bal_retail.weighted_avg_cost}")
        else:
            print("  Transfer already posted; skipping.")

        db.commit()
        print("\nInventory seed complete.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
