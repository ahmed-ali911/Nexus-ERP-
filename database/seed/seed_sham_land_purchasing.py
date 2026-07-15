"""Reference purchasing scenario for Sham Land Food Manufacturing Co.

Demonstrates all three purchasing flows:
  1. PO → GRN → Bill → Payment  (credit purchase of wheat flour)
  2. Direct Receipt, no PO       (cash top-up of packaging cartons)
  3. Purchase Return             (partial return of damaged batch, with approval)

Run inside the backend container:
    uv run --project /app python /database/seed/seed_sham_land_purchasing.py

Idempotent: safe to re-run. Checks existing records before creating new ones.
Prerequisites: seed_organization.py, seed_admin.py, seed_sham_land_master_data.py
"""

import datetime
from decimal import Decimal

from sqlalchemy import and_

from app.core.database import SessionLocal
from app.core.exceptions import ApprovalRequired

# --- Register all table metadata so SQLAlchemy can resolve FKs ---
from app.modules.auth import schemas as auth_schemas
from app.modules.auth import service as auth_service
from app.modules.auth.models import User  # noqa: F401
from app.modules.inventory import service as inv_service
from app.modules.inventory.models import Batch, StockBalance, StockMovement  # noqa: F401
from app.modules.master_data import schemas as md_schemas
from app.modules.master_data import service as md_service
from app.modules.master_data.models import (
    Category,
    PaymentTerms,
    Product,
    ProductType,
    Supplier,
    SupplierType,
    UnitConversion,
    UnitOfMeasure,
)
from app.modules.organization.models import Branch, Company, Warehouse
from app.modules.purchasing import schemas as p_schemas
from app.modules.purchasing import service as p_service
from app.modules.purchasing.models import (
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseFlowPolicy,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseReturn,
    PurchaseReturnLine,
    PurchaseSettings,
    SupplierInvoice,
    SupplierInvoiceLine,
    SupplierPayment,
    SupplierPaymentLine,
)
from app.modules.shared.service import approve_request

BATCH_NUMBER = "WK-FLOUR-001"
SUPPLIER_REF_S1 = "BARK-INV-2026-001"


# ---------------------------------------------------------------------------
# Idempotent fixture helpers
# ---------------------------------------------------------------------------


def _get_company(db, code="SL") -> Company:
    co = db.query(Company).filter_by(code=code).first()
    if co is None:
        raise RuntimeError(f"Company code='{code}' not found. Run seed_organization.py first.")
    return co


def _get_branch(db, company_id) -> Branch:
    br = db.query(Branch).filter_by(company_id=company_id, is_deleted=False).first()
    if br is None:
        raise RuntimeError("No branch found. Run seed_organization.py first.")
    return br


def _get_warehouse(db, branch_id) -> Warehouse:
    # Try the given branch first; fall back to any warehouse in the company's branches
    wh = db.query(Warehouse).filter_by(branch_id=branch_id, is_deleted=False).first()
    if wh is not None:
        return wh
    # Warehouses may belong to a different branch (e.g. Qurain) than the first branch
    branch = db.get(Branch, branch_id)
    wh = (
        db.query(Warehouse)
        .join(Branch, Warehouse.branch_id == Branch.id)
        .filter(Branch.company_id == branch.company_id, Warehouse.is_deleted.is_(False))
        .first()
    )
    if wh is None:
        raise RuntimeError("No warehouse found. Run seed_organization.py first.")
    return wh


def _get_actor(db, company_id) -> User:
    user = db.query(User).filter_by(company_id=company_id, is_deleted=False).first()
    if user is None:
        raise RuntimeError("No user found. Run seed_admin.py first.")
    return user


def _get_or_create_approver(db, company_id, creator_id) -> User:
    approver = (
        db.query(User)
        .filter(
            User.company_id == company_id,
            User.is_deleted.is_(False),
            User.id != creator_id,
        )
        .first()
    )
    if approver is None:
        approver = auth_service.create_user(
            db,
            auth_schemas.UserCreate(
                username="purchasing_approver",
                email="approver@shamland.kw",
                full_name_en="Purchasing Approver",
                full_name_ar="مسؤول الاعتماد",
                password="Approver@123!",
                is_active=True,
                is_superuser=False,
            ),
            company_id=company_id,
            actor_id=creator_id,
        )
        db.flush()
    return approver


def _get_unit(db, company_id, code):
    """Look up an existing unit by code — seeded by seed_sham_land_master_data."""
    u = db.query(UnitOfMeasure).filter_by(company_id=company_id, code=code, is_deleted=False).first()
    if u is None:
        raise RuntimeError(f"Unit code='{code}' not found. Run seed_sham_land_master_data.py first.")
    return u


def _get_or_create_category(db, company_id, code, name_en, name_ar):
    c = db.query(Category).filter_by(company_id=company_id, code=code).first()
    if c is None:
        c = md_service.create_category(
            db,
            md_schemas.CategoryCreate(code=code, name_en=name_en, name_ar=name_ar),
            company_id=company_id,
        )
    return c


def _get_or_create_product(db, company_id, cat_id, base_unit_id, code, name_en, name_ar,
                            batch_tracked=False, purchase_unit_id=None):
    p = db.query(Product).filter_by(company_id=company_id, code=code).first()
    if p is None:
        p = md_service.create_product(
            db,
            md_schemas.ProductCreate(
                code=code,
                name_en=name_en,
                name_ar=name_ar,
                category_id=cat_id,
                product_type=ProductType.RAW_MATERIAL,
                base_unit_id=base_unit_id,
                purchase_unit_id=purchase_unit_id,
                is_batch_tracked=batch_tracked,
            ),
            company_id=company_id,
        )
    return p


def _get_or_create_supplier(db, company_id, code, name_en, name_ar, term_days=30,
                             credit_limit=None):
    s = db.query(Supplier).filter_by(company_id=company_id, code=code).first()
    if s is None:
        s = md_service.create_supplier(
            db,
            md_schemas.SupplierCreate(
                code=code,
                name_en=name_en,
                name_ar=name_ar,
                supplier_type=SupplierType.LOCAL,
                payment_terms=PaymentTerms.CREDIT,
                payment_term_days=term_days,
                credit_limit=credit_limit,
            ),
            company_id=company_id,
        )
    return s


def _get_or_create_conversion(db, company_id, from_id, to_id, factor):
    existing = db.query(UnitConversion).filter_by(
        company_id=company_id, from_unit_id=from_id, to_unit_id=to_id, product_id=None,
        is_deleted=False,
    ).first()
    if existing is None:
        md_service.create_conversion(
            db,
            md_schemas.UnitConversionCreate(
                from_unit_id=from_id, to_unit_id=to_id, factor=Decimal(str(factor))
            ),
            company_id=company_id,
        )


def _find_grn_for_batch(db, company_id, product_id, batch_number):
    """Return (GoodsReceipt, [GoodsReceiptLine]) if batch already received, else None."""
    batch = db.query(Batch).filter_by(
        company_id=company_id, product_id=product_id, batch_number=batch_number
    ).first()
    if batch is None:
        return None
    grn_line = db.query(GoodsReceiptLine).filter_by(batch_id=batch.id).first()
    if grn_line is None:
        return None
    grn = db.query(GoodsReceipt).filter_by(id=grn_line.grn_id).first()
    _, grn_lines = p_service.get_grn_detail(db, grn.id, company_id)
    return grn, grn_lines


def _find_posted_bill_for_grn(db, company_id, grn_id):
    return db.query(SupplierInvoice).filter(
        SupplierInvoice.company_id == company_id,
        SupplierInvoice.goods_receipt_id == grn_id,
        SupplierInvoice.status.in_(["POSTED", "PAID"]),
    ).first()


def _find_posted_grn_for_supplier_product(db, company_id, supplier_id, product_id):
    """Find an existing POSTED GRN for a supplier+product (for direct receipt idempotency)."""
    grn_line = (
        db.query(GoodsReceiptLine)
        .join(GoodsReceipt, GoodsReceipt.id == GoodsReceiptLine.grn_id)
        .filter(
            GoodsReceipt.company_id == company_id,
            GoodsReceipt.supplier_id == supplier_id,
            GoodsReceiptLine.product_id == product_id,
            GoodsReceipt.status == "POSTED",
        )
        .first()
    )
    if grn_line is None:
        return None
    grn = db.query(GoodsReceipt).filter_by(id=grn_line.grn_id).first()
    _, grn_lines = p_service.get_grn_detail(db, grn.id, company_id)
    return grn, grn_lines


def _find_posted_return_for_grn(db, company_id, grn_id):
    return db.query(PurchaseReturn).filter(
        PurchaseReturn.company_id == company_id,
        PurchaseReturn.original_grn_id == grn_id,
        PurchaseReturn.status == "POSTED",
    ).first()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    db = SessionLocal()
    try:
        print("=== Sham Land Purchasing Seed ===\n")

        company = _get_company(db)
        branch = _get_branch(db, company.id)
        wh = _get_warehouse(db, branch.id)
        actor = _get_actor(db, company.id)
        approver = _get_or_create_approver(db, company.id, actor.id)

        print(f"Company  : {company.name_en}")
        print(f"Branch   : {branch.name_en}")
        print(f"WH       : {wh.name_en}")
        print(f"Actor    : {actor.username}")
        print(f"Approver : {approver.username}\n")

        # ── Units — reuse the properly seeded units from seed_sham_land_master_data ──
        gram   = _get_unit(db, company.id, "G")
        kg     = _get_unit(db, company.id, "KG")
        piece  = _get_unit(db, company.id, "PC")
        carton = _get_unit(db, company.id, "CTN")
        # Universal conversions are already seeded; no new ones needed here.

        # ── Categories ───────────────────────────────────────────────────────
        raw_cat = _get_or_create_category(
            db, company.id, "PRAW", "Purchasing - Raw Materials", "مواد خام - مشتريات"
        )
        pkg_cat = _get_or_create_category(
            db, company.id, "PPKG", "Purchasing - Packaging", "تغليف - مشتريات"
        )

        # ── Products ─────────────────────────────────────────────────────────
        flour = _get_or_create_product(
            db, company.id, raw_cat.id, gram.id,
            code="FLOUR-SL", name_en="Wheat Flour", name_ar="دقيق القمح",
            batch_tracked=True, purchase_unit_id=kg.id,
        )
        carton_box = _get_or_create_product(
            db, company.id, pkg_cat.id, piece.id,
            code="PKG-BOX-SL", name_en="Packaging Box", name_ar="علبة تغليف",
            batch_tracked=False, purchase_unit_id=carton.id,
        )

        # ── Suppliers ────────────────────────────────────────────────────────
        al_baraka = _get_or_create_supplier(
            db, company.id,
            code="AL-BARAKA-SL", name_en="Al Baraka Trading", name_ar="شركة البركة للتجارة",
            term_days=30, credit_limit=Decimal("10000"),
        )
        quick_pkg = _get_or_create_supplier(
            db, company.id,
            code="QUICK-PKG-SL", name_en="Quick Packaging Co", name_ar="شركة التغليف السريع",
            term_days=15,
        )

        db.commit()
        print("Fixtures ready.\n")

        # ================================================================
        # SCENARIO 1: PO → GRN → Bill → Payment (credit)
        # ================================================================
        print("─" * 55)
        print("SCENARIO 1: PO → GRN → Bill → Payment (credit)")
        print("─" * 55)

        p_service.update_settings(
            db,
            p_schemas.PurchaseSettingsUpdate(
                purchase_flow_policy=PurchaseFlowPolicy.PO_REQUIRED,
                allow_backdated_purchase_docs=True,
                max_price_variance_pct=Decimal("5"),
            ),
            company_id=company.id,
            actor_id=actor.id,
        )
        db.commit()

        # ── PO ────────────────────────────────────────────────────────────
        existing_grn_result = _find_grn_for_batch(db, company.id, flour.id, BATCH_NUMBER)
        if existing_grn_result:
            grn, grn_lines = existing_grn_result
            print(f"  PO     : (already completed — reusing GRN {grn.grn_number})")
        else:
            po = p_service.create_po(
                db,
                p_schemas.PurchaseOrderCreate(
                    branch_id=branch.id,
                    supplier_id=al_baraka.id,
                    po_date=datetime.date.today(),
                    notes="Wheat flour batch for production week",
                    lines=[
                        p_schemas.POLineCreate(
                            product_id=flour.id,
                            unit_id=kg.id,
                            quantity_ordered=Decimal("500"),
                            unit_cost=Decimal("0.250"),
                        )
                    ],
                ),
                company_id=company.id,
                actor_id=actor.id,
            )
            po = p_service.approve_po(db, po.id, company.id, actor_id=actor.id)
            db.commit()
            print(f"  PO     : {po.po_number}  status={po.status}")

            po_lines = p_service.get_po_detail(db, po.id, company.id)[1]

            grn_obj = p_service.create_grn(
                db,
                p_schemas.GoodsReceiptCreate(
                    branch_id=branch.id,
                    supplier_id=al_baraka.id,
                    purchase_order_id=po.id,
                    receipt_date=datetime.date.today(),
                    notes="Delivery lot " + BATCH_NUMBER,
                    lines=[
                        p_schemas.GRNLineCreate(
                            po_line_id=po_lines[0].id,
                            product_id=flour.id,
                            warehouse_id=wh.id,
                            unit_id=kg.id,
                            quantity_received=Decimal("500"),
                            unit_cost=Decimal("0.250"),
                            batch_number=BATCH_NUMBER,
                            expiry_date=datetime.date.today() + datetime.timedelta(days=365),
                        )
                    ],
                ),
                company_id=company.id,
                actor_id=actor.id,
            )
            grn = p_service.post_grn(db, grn_obj.id, company.id, actor_id=actor.id)
            db.commit()
            _, grn_lines = p_service.get_grn_detail(db, grn.id, company.id)

        print(f"  GRN    : {grn.grn_number}  status={grn.status}")
        print(f"           batch_id={grn_lines[0].batch_id}  mv_id={grn_lines[0].stock_movement_id}")

        balances = inv_service.list_balances(
            db, company.id, warehouse_id=wh.id, product_id=flour.id
        )
        flour_g = sum(b.quantity_on_hand for b in balances)
        print(f"           Flour stock: {flour_g / 1000} KG in ledger")

        # ── Bill ─────────────────────────────────────────────────────────
        existing_bill = _find_posted_bill_for_grn(db, company.id, grn.id)
        if existing_bill:
            bill = existing_bill
            print(f"  Bill   : {bill.bill_number}  (already exists, status={bill.status})")
        else:
            bill = p_service.create_supplier_invoice(
                db,
                p_schemas.SupplierInvoiceCreate(
                    branch_id=branch.id,
                    supplier_id=al_baraka.id,
                    goods_receipt_id=grn.id,
                    purchase_order_id=grn.purchase_order_id,
                    supplier_ref=SUPPLIER_REF_S1,
                    bill_date=datetime.date.today(),
                    notes="Flour invoice",
                    lines=[
                        p_schemas.BillLineCreate(
                            grn_line_id=grn_lines[0].id,
                            product_id=flour.id,
                            unit_id=kg.id,
                            quantity=Decimal("500"),
                            unit_cost=Decimal("0.250"),
                        )
                    ],
                ),
                company_id=company.id,
                actor_id=actor.id,
            )
            bill = p_service.post_supplier_invoice(db, bill.id, company.id, actor_id=actor.id)
            db.commit()
            print(f"  Bill   : {bill.bill_number}  total={bill.grand_total} KWD  due={bill.due_date}")

        # ── Payment ──────────────────────────────────────────────────────
        if bill.status == "PAID":
            print(f"  Payment: (already paid)")
        else:
            payment = p_service.create_supplier_payment(
                db,
                p_schemas.SupplierPaymentCreate(
                    branch_id=branch.id,
                    supplier_id=al_baraka.id,
                    payment_date=datetime.date.today(),
                    total_amount=bill.grand_total,
                    notes=f"Full payment for {bill.bill_number}",
                ),
                company_id=company.id,
                actor_id=actor.id,
            )
            payment = p_service.post_supplier_payment(
                db, payment.id, company.id, actor_id=actor.id
            )
            db.commit()
            db.refresh(bill)
            print(f"  Payment: {payment.payment_number}  amount={payment.total_amount} KWD")

        db.refresh(bill)
        print(f"  Bill status: {bill.status}  ✓ PAID")

        # ================================================================
        # SCENARIO 2: Direct Receipt (no PO)
        # ================================================================
        print()
        print("─" * 55)
        print("SCENARIO 2: Direct Receipt (no PO)")
        print("─" * 55)

        p_service.update_settings(
            db,
            p_schemas.PurchaseSettingsUpdate(
                purchase_flow_policy=PurchaseFlowPolicy.DIRECT_RECEIPT,
            ),
            company_id=company.id,
        )
        db.commit()

        existing_grn2_result = _find_posted_grn_for_supplier_product(
            db, company.id, quick_pkg.id, carton_box.id
        )
        if existing_grn2_result:
            grn2, grn2_lines = existing_grn2_result
            print(f"  GRN    : {grn2.grn_number}  (already posted, reusing)")
        else:
            grn2_obj = p_service.create_grn(
                db,
                p_schemas.GoodsReceiptCreate(
                    branch_id=branch.id,
                    supplier_id=quick_pkg.id,
                    receipt_date=datetime.date.today(),
                    notes="Emergency carton top-up",
                    lines=[
                        p_schemas.GRNLineCreate(
                            product_id=carton_box.id,
                            warehouse_id=wh.id,
                            unit_id=carton.id,   # 1 carton = 24 pieces
                            quantity_received=Decimal("20"),
                            unit_cost=Decimal("1.200"),
                        )
                    ],
                ),
                company_id=company.id,
                actor_id=actor.id,
            )
            grn2 = p_service.post_grn(db, grn2_obj.id, company.id, actor_id=actor.id)
            db.commit()
            _, grn2_lines = p_service.get_grn_detail(db, grn2.id, company.id)
            print(f"  GRN    : {grn2.grn_number}  status={grn2.status}")

        box_balances = inv_service.list_balances(
            db, company.id, warehouse_id=wh.id, product_id=carton_box.id
        )
        total_pcs = sum(b.quantity_on_hand for b in box_balances)
        print(f"           Carton stock: {total_pcs} PC  (20 CTN × 24 = 480 expected)")

        existing_bill2 = _find_posted_bill_for_grn(db, company.id, grn2.id)
        if existing_bill2:
            bill2 = existing_bill2
            print(f"  Bill   : {bill2.bill_number}  (already exists, status={bill2.status})")
        else:
            bill2 = p_service.create_supplier_invoice(
                db,
                p_schemas.SupplierInvoiceCreate(
                    branch_id=branch.id,
                    supplier_id=quick_pkg.id,
                    goods_receipt_id=grn2.id,
                    bill_date=datetime.date.today(),
                    lines=[
                        p_schemas.BillLineCreate(
                            product_id=carton_box.id,
                            unit_id=carton.id,
                            quantity=Decimal("20"),
                            unit_cost=Decimal("1.200"),
                        )
                    ],
                ),
                company_id=company.id,
                actor_id=actor.id,
            )
            bill2 = p_service.post_supplier_invoice(db, bill2.id, company.id, actor_id=actor.id)
            db.commit()
            print(f"  Bill   : {bill2.bill_number}  total={bill2.grand_total} KWD  status={bill2.status}")

        # ================================================================
        # SCENARIO 3: Purchase Return to batch (damaged flour)
        # Maker-checker: actor creates, approver approves.
        # ================================================================
        print()
        print("─" * 55)
        print("SCENARIO 3: Purchase Return to batch (damaged flour)")
        print("─" * 55)

        existing_return = _find_posted_return_for_grn(db, company.id, grn.id)
        if existing_return:
            ret = existing_return
            print(f"  Return : {ret.return_number}  (already posted, status={ret.status})")
        else:
            _, grn1_lines = p_service.get_grn_detail(db, grn.id, company.id)

            ret = p_service.create_purchase_return(
                db,
                p_schemas.PurchaseReturnCreate(
                    branch_id=branch.id,
                    supplier_id=al_baraka.id,
                    original_grn_id=grn.id,
                    return_date=datetime.date.today(),
                    reason="50 KG received with moisture damage — returning to Al Baraka",
                    lines=[
                        p_schemas.ReturnLineCreate(
                            original_grn_line_id=grn1_lines[0].id,
                            quantity_returned=Decimal("50"),   # 50 KG in purchase unit
                        )
                    ],
                ),
                company_id=company.id,
                actor_id=actor.id,
            )
            print(f"  Return : {ret.return_number}  total={ret.total} KWD  status={ret.status}")

            # post_purchase_return ALWAYS requires approval — maker-checker cycle
            try:
                p_service.post_purchase_return(db, ret.id, company.id, actor_id=actor.id)
            except ApprovalRequired as exc:
                print(f"  Approval required (id={exc.approval_request_id})")
                print(f"  Approving as '{approver.username}' (maker-checker) …")
                approve_request(db, exc.approval_request_id, company.id, actor_id=approver.id)
                ret = p_service.post_purchase_return(db, ret.id, company.id, actor_id=actor.id)

            db.commit()
            print(f"           status={ret.status}  ✓ POSTED")

        flour_after = inv_service.list_balances(
            db, company.id, warehouse_id=wh.id, product_id=flour.id
        )
        remaining_kg = sum(b.quantity_on_hand for b in flour_after) / 1000
        print(f"           Flour stock: {remaining_kg} KG  (500 received − 50 returned = 450 expected)")

        print()
        print("=== Purchasing seed COMPLETE ===")

    except Exception as e:
        db.rollback()
        import traceback
        print(f"\nERROR: {e}")
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
