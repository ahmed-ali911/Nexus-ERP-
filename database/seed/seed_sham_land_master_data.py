"""Seed Master Data for the 'Sham Land' reference case: units (WEIGHT/COUNT/
VOLUME) with universal conversions, categories (with a subcategory and a
default Uncategorized fallback), products covering both weight- and
count-based natures (the latter with product-specific carton conversions),
customers, and suppliers. Idempotent.

Depends on seed_organization.py, seed_permissions.py, seed_master_data_catalog.py,
and seed_admin.py having run first.

Run inside the backend container:
    docker-compose exec backend uv run python /database/seed/seed_sham_land_master_data.py
"""

from decimal import Decimal

from app.core.database import SessionLocal
from app.modules.auth.models import User
from app.modules.master_data import schemas, service
from app.modules.master_data.models import (
    Category,
    CustomerType,
    PaymentTerms,
    ProductType,
    SupplierType,
    UnitOfMeasure,
    UnitType,
)
from app.modules.organization.models import Company


def _get_or_create_unit(db, company_id, actor_id, code, name_en, name_ar, symbol, unit_type):
    existing = (
        db.query(UnitOfMeasure).filter(UnitOfMeasure.company_id == company_id, UnitOfMeasure.code == code).first()
    )
    if existing is not None:
        return existing, False
    unit = service.create_unit(
        db,
        schemas.UnitOfMeasureCreate(code=code, name_en=name_en, name_ar=name_ar, symbol=symbol, unit_type=unit_type),
        company_id=company_id,
        actor_id=actor_id,
    )
    return unit, True


def _get_or_create_conversion(db, company_id, actor_id, from_unit, to_unit, factor, product_id=None):
    """product_id=None -> universal rule; set -> product-specific override."""
    existing = service.list_conversions(db, company_id=company_id, product_id=product_id)
    for row in existing:
        if row.product_id == product_id and row.from_unit_id == from_unit.id and row.to_unit_id == to_unit.id:
            return row, False
    conversion = service.create_conversion(
        db,
        schemas.UnitConversionCreate(
            product_id=product_id, from_unit_id=from_unit.id, to_unit_id=to_unit.id, factor=factor
        ),
        company_id=company_id,
        actor_id=actor_id,
    )
    return conversion, True


def _get_or_create_category(db, company_id, actor_id, code, name_en, name_ar, parent_id=None):
    existing = db.query(Category).filter(Category.company_id == company_id, Category.code == code).first()
    if existing is not None:
        return existing, False
    category = service.create_category(
        db,
        schemas.CategoryCreate(code=code, name_en=name_en, name_ar=name_ar, parent_id=parent_id),
        company_id=company_id,
        actor_id=actor_id,
    )
    return category, True


def _get_or_create_product(db, company_id, actor_id, code, **kwargs):
    existing = service.list_products(db, company_id=company_id)
    for row in existing:
        if row.code == code:
            return row, False
    product = service.create_product(
        db, schemas.ProductCreate(code=code, **kwargs), company_id=company_id, actor_id=actor_id
    )
    return product, True


def _get_or_create_customer(db, company_id, actor_id, code, **kwargs):
    existing = service.list_customers(db, company_id=company_id)
    for row in existing:
        if row.code == code:
            return row, False
    customer = service.create_customer(
        db, schemas.CustomerCreate(code=code, **kwargs), company_id=company_id, actor_id=actor_id
    )
    return customer, True


def _get_or_create_supplier(db, company_id, actor_id, code, **kwargs):
    existing = service.list_suppliers(db, company_id=company_id)
    for row in existing:
        if row.code == code:
            return row, False
    supplier = service.create_supplier(
        db, schemas.SupplierCreate(code=code, **kwargs), company_id=company_id, actor_id=actor_id
    )
    return supplier, True


def run() -> None:
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.code == "SL").first()
        if company is None:
            print("Company 'SL' not found -- run seed_organization.py first.")
            return
        admin = db.query(User).filter(User.company_id == company.id, User.username == "admin").first()
        actor_id = admin.id if admin is not None else None

        # --- Units -----------------------------------------------------
        gram, created = _get_or_create_unit(db, company.id, actor_id, "G", "Gram", "غرام", "g", UnitType.WEIGHT)
        print(f"{'Created' if created else 'Exists'}: unit {gram.code}")
        kg, created = _get_or_create_unit(db, company.id, actor_id, "KG", "Kilogram", "كيلوغرام", "kg", UnitType.WEIGHT)
        print(f"{'Created' if created else 'Exists'}: unit {kg.code}")
        ton, created = _get_or_create_unit(db, company.id, actor_id, "TON", "Ton", "طن", "t", UnitType.WEIGHT)
        print(f"{'Created' if created else 'Exists'}: unit {ton.code}")

        piece, created = _get_or_create_unit(db, company.id, actor_id, "PC", "Piece", "قطعة", "pc", UnitType.COUNT)
        print(f"{'Created' if created else 'Exists'}: unit {piece.code}")
        carton, created = _get_or_create_unit(db, company.id, actor_id, "CTN", "Carton", "كرتون", "ctn", UnitType.COUNT)
        print(f"{'Created' if created else 'Exists'}: unit {carton.code}")
        box, created = _get_or_create_unit(db, company.id, actor_id, "BOX", "Box", "صندوق", "bx", UnitType.COUNT)
        print(f"{'Created' if created else 'Exists'}: unit {box.code}")
        dozen, created = _get_or_create_unit(db, company.id, actor_id, "DZ", "Dozen", "دستة", "dz", UnitType.COUNT)
        print(f"{'Created' if created else 'Exists'}: unit {dozen.code}")

        liter, created = _get_or_create_unit(db, company.id, actor_id, "L", "Liter", "لتر", "L", UnitType.VOLUME)
        print(f"{'Created' if created else 'Exists'}: unit {liter.code}")
        ml, created = _get_or_create_unit(db, company.id, actor_id, "ML", "Milliliter", "مليلتر", "ml", UnitType.VOLUME)
        print(f"{'Created' if created else 'Exists'}: unit {ml.code}")

        # --- Universal conversions --------------------------------------
        # ton<->kg is seeded directly (not just ton<->g) since resolution is
        # direct-pair-only, no multi-hop chaining -- see design notes.
        for from_u, to_u, factor in (
            (kg, gram, Decimal("1000")),
            (ton, gram, Decimal("1000000")),
            (ton, kg, Decimal("1000")),
            (dozen, piece, Decimal("12")),
            (liter, ml, Decimal("1000")),
        ):
            _, created = _get_or_create_conversion(db, company.id, actor_id, from_u, to_u, factor)
            print(f"{'Created' if created else 'Exists'}: conversion {from_u.code}->{to_u.code} = {factor}")

        # --- Categories --------------------------------------------------
        uncategorized, created = _get_or_create_category(
            db, company.id, actor_id, "UNCATEGORIZED", "Uncategorized", "غير مصنّف"
        )
        print(f"{'Created' if created else 'Exists'}: category {uncategorized.code}")

        nuts, created = _get_or_create_category(db, company.id, actor_id, "NUTS", "Nuts", "المكسرات")
        print(f"{'Created' if created else 'Exists'}: category {nuts.code}")
        almonds, created = _get_or_create_category(
            db, company.id, actor_id, "ALMONDS", "Almonds", "اللوز", parent_id=nuts.id
        )
        print(f"{'Created' if created else 'Exists'}: category {almonds.code} (parent={nuts.code})")

        coffee, created = _get_or_create_category(db, company.id, actor_id, "COFFEE", "Coffee", "القهوة")
        print(f"{'Created' if created else 'Exists'}: category {coffee.code}")
        chocolate, created = _get_or_create_category(db, company.id, actor_id, "CHOCOLATE", "Chocolate", "الشوكولاتة")
        print(f"{'Created' if created else 'Exists'}: category {chocolate.code}")
        dried_fruits, created = _get_or_create_category(
            db, company.id, actor_id, "DRIED_FRUITS", "Dried Fruits", "فواكه مجففة"
        )
        print(f"{'Created' if created else 'Exists'}: category {dried_fruits.code}")
        dates, created = _get_or_create_category(db, company.id, actor_id, "DATES", "Dates", "التمور")
        print(f"{'Created' if created else 'Exists'}: category {dates.code}")

        # --- Products (WEIGHT-based) -------------------------------------
        green_coffee, created = _get_or_create_product(
            db,
            company.id,
            actor_id,
            "GREEN-COFFEE",
            name_en="Yemeni Green Coffee Beans",
            name_ar="بن أخضر يمني",
            category_id=coffee.id,
            product_type=ProductType.RAW_MATERIAL,
            base_unit_id=gram.id,
        )
        print(f"{'Created' if created else 'Exists'}: product {green_coffee.code}")

        roasted_coffee, created = _get_or_create_product(
            db,
            company.id,
            actor_id,
            "ROASTED-COFFEE",
            name_en="Roasted Coffee - Medium Roast",
            name_ar="قهوة محمصة - تحميص متوسط",
            category_id=coffee.id,
            product_type=ProductType.FINISHED_GOOD,
            base_unit_id=gram.id,
            sales_unit_id=kg.id,
        )
        print(f"{'Created' if created else 'Exists'}: product {roasted_coffee.code}")

        roasted_almonds, created = _get_or_create_product(
            db,
            company.id,
            actor_id,
            "ROASTED-ALMONDS",
            name_en="Roasted Almonds",
            name_ar="لوز محمص",
            category_id=almonds.id,
            product_type=ProductType.FINISHED_GOOD,
            base_unit_id=gram.id,
            sales_unit_id=kg.id,
        )
        print(f"{'Created' if created else 'Exists'}: product {roasted_almonds.code}")

        # --- Products (COUNT-based, product-specific carton conversions) -
        mixed_nuts_box, created = _get_or_create_product(
            db,
            company.id,
            actor_id,
            "MIXED-NUTS-BOX",
            name_en="Mixed Nuts Gift Box",
            name_ar="علبة مكسرات مشكلة",
            category_id=nuts.id,
            product_type=ProductType.FINISHED_GOOD,
            base_unit_id=piece.id,
            purchase_unit_id=carton.id,
        )
        print(f"{'Created' if created else 'Exists'}: product {mixed_nuts_box.code}")
        _, created = _get_or_create_conversion(
            db, company.id, actor_id, carton, piece, Decimal("12"), product_id=mixed_nuts_box.id
        )
        print(
            f"{'Created' if created else 'Exists'}: conversion {carton.code}->{piece.code} = 12 "
            f"(product-specific: {mixed_nuts_box.code})"
        )

        dried_apricot_pack, created = _get_or_create_product(
            db,
            company.id,
            actor_id,
            "DRIED-APRICOT-PACK",
            name_en="Dried Apricot Pack",
            name_ar="عبوة مشمش مجفف",
            category_id=dried_fruits.id,
            product_type=ProductType.FINISHED_GOOD,
            base_unit_id=piece.id,
            purchase_unit_id=carton.id,
        )
        print(f"{'Created' if created else 'Exists'}: product {dried_apricot_pack.code}")
        _, created = _get_or_create_conversion(
            db, company.id, actor_id, carton, piece, Decimal("24"), product_id=dried_apricot_pack.id
        )
        print(
            f"{'Created' if created else 'Exists'}: conversion {carton.code}->{piece.code} = 24 "
            f"(product-specific: {dried_apricot_pack.code})"
        )

        # --- Customers -----------------------------------------------------
        rawda_shop, created = _get_or_create_customer(
            db,
            company.id,
            actor_id,
            "RAWDA-SHOP",
            name_en="Al-Rawda Grocery",
            name_ar="بقالة الروضة",
            customer_type=CustomerType.SHOP,
            payment_terms=PaymentTerms.CASH,
        )
        print(f"{'Created' if created else 'Exists'}: customer {rawda_shop.code}")

        sultan_center, created = _get_or_create_customer(
            db,
            company.id,
            actor_id,
            "SULTAN-CENTER",
            name_en="Sultan Center",
            name_ar="مركز سلطان",
            customer_type=CustomerType.COMPANY,
            payment_terms=PaymentTerms.CREDIT,
            credit_limit=Decimal("5000.000"),
        )
        print(f"{'Created' if created else 'Exists'}: customer {sultan_center.code}")

        # --- Suppliers -----------------------------------------------------
        local_roasters, created = _get_or_create_supplier(
            db,
            company.id,
            actor_id,
            "KW-ROASTERS",
            name_en="Kuwait Local Roasters",
            name_ar="محامص الكويت المحلية",
            supplier_type=SupplierType.LOCAL,
            payment_terms=PaymentTerms.CASH,
        )
        print(f"{'Created' if created else 'Exists'}: supplier {local_roasters.code}")

        brazil_exports, created = _get_or_create_supplier(
            db,
            company.id,
            actor_id,
            "BR-COFFEE",
            name_en="Brazil Coffee Exports",
            name_ar="صادرات القهوة البرازيلية",
            supplier_type=SupplierType.IMPORT,
            payment_terms=PaymentTerms.CREDIT,
        )
        print(f"{'Created' if created else 'Exists'}: supplier {brazil_exports.code}")

        db.commit()
        print("Seed complete.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
