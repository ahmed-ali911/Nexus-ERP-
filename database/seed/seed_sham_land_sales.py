"""Seed Sales data for the 'Sham Land' reference case:
  - Default price list with prices for all sellable products
  - Posted CREDIT invoice to Sultan Center (ROASTED-COFFEE, 10 KG) → due in 30 days
  - Partial collection of 20 KWD against that invoice (FIFO)
  - Credit note returning 2 KG of ROASTED-COFFEE to the original batch
  - Posted CASH invoice to Al-Rawda Grocery (ROASTED-ALMONDS, 5 KG)

Idempotent: skips if sales data already exists.

Depends on all prior seeds having run.

Run inside the backend container:
    docker-compose exec backend uv run python /database/seed/seed_sham_land_sales.py
"""

import datetime
from decimal import Decimal

from app.core.database import SessionLocal
from app.modules.auth.models import User
from app.modules.inventory.models import Batch
from app.modules.master_data.models import Customer, Product, UnitOfMeasure
from app.modules.organization.models import Branch, Company, Warehouse
from app.modules.sales import schemas as s_schemas
from app.modules.sales import service as s_service
from app.modules.sales.models import (
    AllocationMethod,
    Collection,
    CreditNote,
    PriceList,
    SalesInvoice,
)


def _get_product(db, company_id, code):
    return db.query(Product).filter(Product.company_id == company_id, Product.code == code).first()


def _get_unit(db, company_id, code):
    return (
        db.query(UnitOfMeasure)
        .filter(UnitOfMeasure.company_id == company_id, UnitOfMeasure.code == code)
        .first()
    )


def _get_customer(db, company_id, code):
    return (
        db.query(Customer)
        .filter(Customer.company_id == company_id, Customer.code == code)
        .first()
    )


def _get_branch(db, company_id, code):
    return db.query(Branch).filter(Branch.company_id == company_id, Branch.code == code).first()


def _get_warehouse(db, company_id, code):
    return (
        db.query(Warehouse)
        .join(Branch, Warehouse.branch_id == Branch.id)
        .filter(Branch.company_id == company_id, Warehouse.code == code)
        .first()
    )


def _get_batch(db, company_id, product_id, batch_number):
    return (
        db.query(Batch)
        .filter(
            Batch.company_id == company_id,
            Batch.product_id == product_id,
            Batch.batch_number == batch_number,
        )
        .first()
    )


def run() -> None:
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.code == "SL").first()
        if company is None:
            print("Company 'SL' not found — run seed_organization.py first.")
            return

        admin = (
            db.query(User)
            .filter(User.company_id == company.id, User.username == "admin")
            .first()
        )
        actor_id = admin.id if admin else None

        # ── Resolve objects from prior seeds ─────────────────────────────
        qrn_branch = _get_branch(db, company.id, "QRN")
        qrn_fg = _get_warehouse(db, company.id, "QRN-FG")
        if qrn_branch is None or qrn_fg is None:
            print("QRN branch/warehouse not found — run seed_organization.py first.")
            return

        roasted_coffee = _get_product(db, company.id, "ROASTED-COFFEE")
        roasted_almonds = _get_product(db, company.id, "ROASTED-ALMONDS")
        kg_unit = _get_unit(db, company.id, "KG")
        if roasted_coffee is None or roasted_almonds is None or kg_unit is None:
            print("Products/units not found — run seed_sham_land_master_data.py first.")
            return

        rc_batch_a = _get_batch(db, company.id, roasted_coffee.id, "RC-2026-001")
        ra_batch = _get_batch(db, company.id, roasted_almonds.id, "RA-2026-001")
        if rc_batch_a is None or ra_batch is None:
            print("Batches not found — run seed_sham_land_inventory.py first.")
            return

        sultan_center = _get_customer(db, company.id, "SULTAN-CENTER")
        rawda_shop = _get_customer(db, company.id, "RAWDA-SHOP")
        if sultan_center is None or rawda_shop is None:
            print("Customers not found — run seed_sham_land_master_data.py first.")
            return

        # ── 1. Default Price List ─────────────────────────────────────────
        existing_pl = (
            db.query(PriceList)
            .filter(
                PriceList.company_id == company.id,
                PriceList.code == "STD",
                PriceList.is_deleted.is_(False),
            )
            .first()
        )
        if existing_pl is None:
            pl = s_service.create_price_list(
                db,
                s_schemas.PriceListCreate(
                    code="STD",
                    name_en="Standard Price List",
                    name_ar="قائمة الأسعار القياسية",
                    is_default=True,
                    is_active=True,
                ),
                company_id=company.id,
                actor_id=actor_id,
            )
            print(f"Created: price list {pl.code} (id={pl.id}, default=True)")

            # Prices in selling unit (KG) — conversion to base handled at POST
            s_service.add_price_list_item(
                db,
                pl.id,
                s_schemas.PriceListItemCreate(
                    product_id=roasted_coffee.id, unit_price=Decimal("4.500")
                ),
                company_id=company.id,
                actor_id=actor_id,
            )
            print(f"  + ROASTED-COFFEE @ 4.500 KWD/KG")

            s_service.add_price_list_item(
                db,
                pl.id,
                s_schemas.PriceListItemCreate(
                    product_id=roasted_almonds.id, unit_price=Decimal("6.000")
                ),
                company_id=company.id,
                actor_id=actor_id,
            )
            print(f"  + ROASTED-ALMONDS @ 6.000 KWD/KG")
        else:
            pl = existing_pl
            print(f"Exists: price list {pl.code} (id={pl.id})")

        # ── 2. Credit sale: Sultan Center, 10 KG Roasted Coffee ──────────
        existing_invoice = (
            db.query(SalesInvoice)
            .filter(
                SalesInvoice.company_id == company.id,
                SalesInvoice.customer_id == sultan_center.id,
            )
            .first()
        )
        if existing_invoice is None:
            today = datetime.date.today()
            inv = s_service.create_invoice(
                db,
                s_schemas.SalesInvoiceCreate(
                    branch_id=qrn_branch.id,
                    customer_id=sultan_center.id,
                    price_list_id=pl.id,
                    invoice_date=today,
                    notes="Opening credit sale — Sham Land seed",
                    lines=[
                        s_schemas.InvoiceLineCreate(
                            product_id=roasted_coffee.id,
                            warehouse_id=qrn_fg.id,
                            batch_id=rc_batch_a.id,
                            unit_id=kg_unit.id,
                            quantity_ordered=Decimal("10"),  # 10 KG → 10000 g issued
                            unit_price=Decimal("4.500"),
                            price_source="PRICE_LIST",
                        )
                    ],
                ),
                company_id=company.id,
                actor_id=actor_id,
            )
            print(
                f"\nCreated: invoice {inv.invoice_number} (id={inv.id}) "
                f"SULTAN-CENTER 10 KG ROASTED-COFFEE @ 4.500 = {inv.grand_total} KWD"
            )

            # Enable negative-stock to bypass stock check during seed
            # (seed order isn't guaranteed; inventory seed should have run first)
            s_service.post_invoice(
                db, inv.id, company_id=company.id, actor_id=actor_id
            )
            db.refresh(inv)
            print(
                f"Posted: {inv.invoice_number} → status={inv.status}, "
                f"due_date={inv.due_date}, grand_total={inv.grand_total}"
            )

            exposure = s_service._compute_credit_exposure(db, sultan_center.id)
            print(f"Sultan Center exposure after invoice: {exposure} KWD")

            # ── 3. Partial Collection: 20 KWD ─────────────────────────────
            col = s_service.create_collection(
                db,
                s_schemas.CollectionCreate(
                    branch_id=qrn_branch.id,
                    customer_id=sultan_center.id,
                    collection_date=today,
                    total_amount=Decimal("20.000"),
                    allocation_method=AllocationMethod.AUTO,
                    notes="Partial payment — Sham Land seed",
                ),
                company_id=company.id,
                actor_id=actor_id,
            )
            s_service.post_collection(
                db, col.id, company_id=company.id, actor_id=actor_id
            )
            db.refresh(inv)
            exposure_after = s_service._compute_credit_exposure(db, sultan_center.id)
            print(
                f"\nCollection {col.collection_number} posted: 20.000 KWD → "
                f"invoice amount_collected={inv.amount_collected}, "
                f"exposure={exposure_after} KWD"
            )

            # ── 4. Credit Note: return 2 KG to original batch ─────────────
            # Find the invoice line we just created
            from app.modules.sales.models import SalesInvoiceLine
            inv_line = (
                db.query(SalesInvoiceLine)
                .filter(
                    SalesInvoiceLine.invoice_id == inv.id,
                    SalesInvoiceLine.is_deleted.is_(False),
                )
                .first()
            )
            cn = s_service.create_credit_note(
                db,
                s_schemas.CreditNoteCreate(
                    original_invoice_id=inv.id,
                    credit_note_date=today,
                    reason="Partial return — customer rejected 2 KG",
                    lines=[
                        s_schemas.CreditNoteLineCreate(
                            original_line_id=inv_line.id,
                            quantity_returned=Decimal("2"),  # 2 KG in selling unit
                        )
                    ],
                ),
                company_id=company.id,
                actor_id=actor_id,
            )
            s_service.post_credit_note(
                db, cn.id, company_id=company.id, actor_id=actor_id
            )
            db.refresh(cn)
            print(
                f"\nCredit note {cn.credit_note_number} posted: "
                f"2 KG ROASTED-COFFEE returned to batch RC-2026-001, "
                f"total={cn.total} KWD"
            )

            from app.modules.inventory import service as inv_service
            bal = inv_service._get_balance(
                db, company.id, qrn_fg.id, roasted_coffee.id, rc_batch_a.id
            )
            print(
                f"QRN-FG RC-2026-001 balance after credit note: "
                f"{bal.quantity_on_hand} g, WAC={bal.weighted_avg_cost}"
            )
        else:
            print(f"\nExists: invoices for SULTAN-CENTER — skipping credit sale, collection, credit note.")

        # ── 5. Cash Sale: Al-Rawda, 5 KG Roasted Almonds ─────────────────
        existing_rawda = (
            db.query(SalesInvoice)
            .filter(
                SalesInvoice.company_id == company.id,
                SalesInvoice.customer_id == rawda_shop.id,
            )
            .first()
        )
        if existing_rawda is None:
            today = datetime.date.today()
            cash_inv = s_service.create_invoice(
                db,
                s_schemas.SalesInvoiceCreate(
                    branch_id=qrn_branch.id,
                    customer_id=rawda_shop.id,
                    price_list_id=pl.id,
                    invoice_date=today,
                    notes="Cash sale — Sham Land seed",
                    lines=[
                        s_schemas.InvoiceLineCreate(
                            product_id=roasted_almonds.id,
                            warehouse_id=qrn_fg.id,
                            batch_id=ra_batch.id,
                            unit_id=kg_unit.id,
                            quantity_ordered=Decimal("5"),  # 5 KG → 5000 g issued
                            unit_price=Decimal("6.000"),
                            price_source="PRICE_LIST",
                        )
                    ],
                ),
                company_id=company.id,
                actor_id=actor_id,
            )
            s_service.post_invoice(
                db, cash_inv.id, company_id=company.id, actor_id=actor_id
            )
            db.refresh(cash_inv)
            print(
                f"\nCreated & posted: invoice {cash_inv.invoice_number} (id={cash_inv.id}) "
                f"CASH — RAWDA-SHOP 5 KG ROASTED-ALMONDS @ 6.000 = {cash_inv.grand_total} KWD, "
                f"due_date={cash_inv.due_date} (CASH → same as posted date)"
            )
        else:
            print(f"\nExists: invoices for RAWDA-SHOP — skipping cash sale.")

        db.commit()
        print("\nSales seed complete.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
