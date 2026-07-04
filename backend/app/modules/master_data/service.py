from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleViolation, NotFoundError

from . import models, schemas

# --- Internal helpers --------------------------------------------------


def _get_scoped(db: Session, model, entity_id: int, company_id: int, label: str):
    """Fetch a row and verify it belongs to the given company.

    A cross-company reference is treated identically to "not found" (404,
    not 403) so a caller can't learn that a given ID exists in someone
    else's company.
    """
    entity = db.get(model, entity_id)
    if entity is None or entity.company_id != company_id:
        raise NotFoundError(f"{label} {entity_id} not found")
    return entity


def _assert_same_unit_type(unit_a: models.UnitOfMeasure, unit_b: models.UnitOfMeasure) -> None:
    if unit_a.unit_type != unit_b.unit_type:
        raise BusinessRuleViolation(
            f"Cannot relate units of different types: {unit_a.code} ({unit_a.unit_type}) "
            f"vs {unit_b.code} ({unit_b.unit_type})"
        )


def _assert_base_unit_mutable(db: Session, product: models.Product, new_base_unit_id: int) -> None:
    from app.modules.inventory.models import StockMovement  # lazy: avoids circular import

    has_movements = db.scalars(
        select(StockMovement).where(StockMovement.product_id == product.id).limit(1)
    ).first()
    if has_movements is not None:
        raise BusinessRuleViolation(
            f"Cannot change base unit for product {product.code}: stock movements already exist"
        )


# --- Units of Measure ----------------------------------------------------


def create_unit(
    db: Session, payload: schemas.UnitOfMeasureCreate, company_id: int, actor_id: int | None = None
) -> models.UnitOfMeasure:
    unit = models.UnitOfMeasure(
        company_id=company_id,
        code=payload.code,
        name_en=payload.name_en,
        name_ar=payload.name_ar,
        symbol=payload.symbol,
        unit_type=payload.unit_type,
        is_active=payload.is_active,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(unit)
    db.flush()
    return unit


def get_unit(db: Session, unit_id: int) -> models.UnitOfMeasure:
    unit = db.get(models.UnitOfMeasure, unit_id)
    if unit is None:
        raise NotFoundError(f"Unit {unit_id} not found")
    return unit


def list_units(
    db: Session, company_id: int, include_deleted: bool = False
) -> list[models.UnitOfMeasure]:
    stmt = select(models.UnitOfMeasure).where(models.UnitOfMeasure.company_id == company_id)
    if not include_deleted:
        stmt = stmt.where(models.UnitOfMeasure.is_deleted.is_(False))
    return list(db.scalars(stmt.order_by(models.UnitOfMeasure.id)))


def update_unit(
    db: Session, unit_id: int, payload: schemas.UnitOfMeasureUpdate, actor_id: int | None = None
) -> models.UnitOfMeasure:
    unit = get_unit(db, unit_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(unit, field, value)
    unit.updated_by = actor_id
    db.flush()
    return unit


def soft_delete_unit(
    db: Session, unit_id: int, actor_id: int | None = None
) -> models.UnitOfMeasure:
    unit = get_unit(db, unit_id)
    if unit.is_deleted:
        return unit
    unit.is_deleted = True
    unit.deleted_at = datetime.datetime.now(datetime.UTC)
    unit.updated_by = actor_id
    db.flush()
    return unit


def restore_unit(db: Session, unit_id: int, actor_id: int | None = None) -> models.UnitOfMeasure:
    unit = get_unit(db, unit_id)
    if not unit.is_deleted:
        return unit
    unit.is_deleted = False
    unit.deleted_at = None
    unit.updated_by = actor_id
    db.flush()
    return unit


# --- Categories --------------------------------------------------------


def _assert_no_cycle(db: Session, category_id: int, new_parent_id: int) -> None:
    current_id: int | None = new_parent_id
    visited: set[int] = set()
    while current_id is not None:
        if current_id == category_id:
            raise BusinessRuleViolation("Category cannot be its own ancestor")
        if current_id in visited:
            break  # defensive: shouldn't happen with valid data
        visited.add(current_id)
        parent = db.get(models.Category, current_id)
        current_id = parent.parent_id if parent is not None else None


def create_category(
    db: Session, payload: schemas.CategoryCreate, company_id: int, actor_id: int | None = None
) -> models.Category:
    if payload.parent_id is not None:
        _get_scoped(db, models.Category, payload.parent_id, company_id, "Category")
    category = models.Category(
        company_id=company_id,
        code=payload.code,
        name_en=payload.name_en,
        name_ar=payload.name_ar,
        parent_id=payload.parent_id,
        is_active=payload.is_active,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(category)
    db.flush()
    return category


def get_category(db: Session, category_id: int) -> models.Category:
    category = db.get(models.Category, category_id)
    if category is None:
        raise NotFoundError(f"Category {category_id} not found")
    return category


def list_categories(
    db: Session, company_id: int, include_deleted: bool = False
) -> list[models.Category]:
    stmt = select(models.Category).where(models.Category.company_id == company_id)
    if not include_deleted:
        stmt = stmt.where(models.Category.is_deleted.is_(False))
    return list(db.scalars(stmt.order_by(models.Category.id)))


def update_category(
    db: Session, category_id: int, payload: schemas.CategoryUpdate, actor_id: int | None = None
) -> models.Category:
    category = get_category(db, category_id)
    data = payload.model_dump(exclude_unset=True)

    if "parent_id" in data and data["parent_id"] is not None:
        _get_scoped(db, models.Category, data["parent_id"], category.company_id, "Category")
        _assert_no_cycle(db, category_id, data["parent_id"])

    for field, value in data.items():
        setattr(category, field, value)
    category.updated_by = actor_id
    db.flush()
    return category


def soft_delete_category(
    db: Session, category_id: int, actor_id: int | None = None
) -> models.Category:
    category = get_category(db, category_id)
    if category.is_deleted:
        return category
    category.is_deleted = True
    category.deleted_at = datetime.datetime.now(datetime.UTC)
    category.updated_by = actor_id
    db.flush()
    return category


def restore_category(db: Session, category_id: int, actor_id: int | None = None) -> models.Category:
    category = get_category(db, category_id)
    if not category.is_deleted:
        return category
    category.is_deleted = False
    category.deleted_at = None
    category.updated_by = actor_id
    db.flush()
    return category


# --- Products ------------------------------------------------------------


def create_product(
    db: Session, payload: schemas.ProductCreate, company_id: int, actor_id: int | None = None
) -> models.Product:
    _get_scoped(db, models.Category, payload.category_id, company_id, "Category")
    base_unit = _get_scoped(db, models.UnitOfMeasure, payload.base_unit_id, company_id, "Unit")

    if payload.purchase_unit_id is not None:
        purchase_unit = _get_scoped(
            db, models.UnitOfMeasure, payload.purchase_unit_id, company_id, "Unit"
        )
        _assert_same_unit_type(base_unit, purchase_unit)

    if payload.sales_unit_id is not None:
        sales_unit = _get_scoped(
            db, models.UnitOfMeasure, payload.sales_unit_id, company_id, "Unit"
        )
        _assert_same_unit_type(base_unit, sales_unit)

    product = models.Product(
        company_id=company_id,
        code=payload.code,
        name_en=payload.name_en,
        name_ar=payload.name_ar,
        category_id=payload.category_id,
        product_type=payload.product_type,
        base_unit_id=payload.base_unit_id,
        purchase_unit_id=payload.purchase_unit_id,
        sales_unit_id=payload.sales_unit_id,
        barcode=payload.barcode,
        is_active=payload.is_active,
        is_sellable=payload.is_sellable,
        is_purchasable=payload.is_purchasable,
        is_stockable=payload.is_stockable,
        is_batch_tracked=payload.is_batch_tracked,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(product)
    db.flush()
    return product


def get_product(db: Session, product_id: int) -> models.Product:
    product = db.get(models.Product, product_id)
    if product is None:
        raise NotFoundError(f"Product {product_id} not found")
    return product


def list_products(
    db: Session, company_id: int, category_id: int | None = None, include_deleted: bool = False
) -> list[models.Product]:
    stmt = select(models.Product).where(models.Product.company_id == company_id)
    if category_id is not None:
        stmt = stmt.where(models.Product.category_id == category_id)
    if not include_deleted:
        stmt = stmt.where(models.Product.is_deleted.is_(False))
    return list(db.scalars(stmt.order_by(models.Product.id)))


def update_product(
    db: Session, product_id: int, payload: schemas.ProductUpdate, actor_id: int | None = None
) -> models.Product:
    product = get_product(db, product_id)
    data = payload.model_dump(exclude_unset=True)

    new_base_unit_id = data.get("base_unit_id", product.base_unit_id)
    if new_base_unit_id != product.base_unit_id:
        _assert_base_unit_mutable(db, product, new_base_unit_id)
    base_unit = _get_scoped(db, models.UnitOfMeasure, new_base_unit_id, product.company_id, "Unit")

    new_purchase_unit_id = data.get("purchase_unit_id", product.purchase_unit_id)
    if new_purchase_unit_id is not None:
        purchase_unit = _get_scoped(
            db, models.UnitOfMeasure, new_purchase_unit_id, product.company_id, "Unit"
        )
        _assert_same_unit_type(base_unit, purchase_unit)

    new_sales_unit_id = data.get("sales_unit_id", product.sales_unit_id)
    if new_sales_unit_id is not None:
        sales_unit = _get_scoped(
            db, models.UnitOfMeasure, new_sales_unit_id, product.company_id, "Unit"
        )
        _assert_same_unit_type(base_unit, sales_unit)

    if "category_id" in data:
        _get_scoped(db, models.Category, data["category_id"], product.company_id, "Category")

    for field, value in data.items():
        setattr(product, field, value)
    product.updated_by = actor_id
    db.flush()
    return product


def soft_delete_product(
    db: Session, product_id: int, actor_id: int | None = None
) -> models.Product:
    product = get_product(db, product_id)
    if product.is_deleted:
        return product
    product.is_deleted = True
    product.deleted_at = datetime.datetime.now(datetime.UTC)
    product.updated_by = actor_id
    db.flush()
    return product


def restore_product(db: Session, product_id: int, actor_id: int | None = None) -> models.Product:
    product = get_product(db, product_id)
    if not product.is_deleted:
        return product
    product.is_deleted = False
    product.deleted_at = None
    product.updated_by = actor_id
    db.flush()
    return product


# --- Unit Conversions ------------------------------------------------------


def _find_conversion_row(
    db: Session, company_id: int, product_id: int | None, from_unit_id: int, to_unit_id: int
) -> models.UnitConversion | None:
    product_filter = (
        models.UnitConversion.product_id.is_(None)
        if product_id is None
        else models.UnitConversion.product_id == product_id
    )
    stmt = select(models.UnitConversion).where(
        models.UnitConversion.company_id == company_id,
        product_filter,
        models.UnitConversion.from_unit_id == from_unit_id,
        models.UnitConversion.to_unit_id == to_unit_id,
        models.UnitConversion.is_deleted.is_(False),
    )
    return db.scalars(stmt).first()


def get_conversion_factor(
    db: Session, company_id: int, from_unit_id: int, to_unit_id: int, product_id: int | None = None
) -> Decimal:
    """Resolve the factor F such that `1 from_unit == F to_unit`.

    Direct pairs only (no multi-hop/transitive chaining -- see design notes).
    Checks product-specific rows before falling back to universal ones, and
    tries the reverse-stored direction (inverting the factor) before giving
    up.
    """
    if from_unit_id == to_unit_id:
        return Decimal(1)

    if product_id is not None:
        row = _find_conversion_row(db, company_id, product_id, from_unit_id, to_unit_id)
        if row is not None:
            return row.factor
        row = _find_conversion_row(db, company_id, product_id, to_unit_id, from_unit_id)
        if row is not None:
            return Decimal(1) / row.factor

    row = _find_conversion_row(db, company_id, None, from_unit_id, to_unit_id)
    if row is not None:
        return row.factor
    row = _find_conversion_row(db, company_id, None, to_unit_id, from_unit_id)
    if row is not None:
        return Decimal(1) / row.factor

    raise NotFoundError(f"No conversion path from unit {from_unit_id} to unit {to_unit_id}")


def create_conversion(
    db: Session, payload: schemas.UnitConversionCreate, company_id: int, actor_id: int | None = None
) -> models.UnitConversion:
    from_unit = _get_scoped(db, models.UnitOfMeasure, payload.from_unit_id, company_id, "Unit")
    to_unit = _get_scoped(db, models.UnitOfMeasure, payload.to_unit_id, company_id, "Unit")
    _assert_same_unit_type(from_unit, to_unit)

    if payload.product_id is not None:
        _get_scoped(db, models.Product, payload.product_id, company_id, "Product")

    conversion = models.UnitConversion(
        company_id=company_id,
        product_id=payload.product_id,
        from_unit_id=payload.from_unit_id,
        to_unit_id=payload.to_unit_id,
        factor=payload.factor,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(conversion)
    db.flush()
    return conversion


def get_conversion(db: Session, conversion_id: int) -> models.UnitConversion:
    conversion = db.get(models.UnitConversion, conversion_id)
    if conversion is None:
        raise NotFoundError(f"Unit conversion {conversion_id} not found")
    return conversion


def list_conversions(
    db: Session, company_id: int, product_id: int | None = None, include_deleted: bool = False
) -> list[models.UnitConversion]:
    stmt = select(models.UnitConversion).where(models.UnitConversion.company_id == company_id)
    if product_id is not None:
        stmt = stmt.where(models.UnitConversion.product_id == product_id)
    if not include_deleted:
        stmt = stmt.where(models.UnitConversion.is_deleted.is_(False))
    return list(db.scalars(stmt.order_by(models.UnitConversion.id)))


def update_conversion(
    db: Session,
    conversion_id: int,
    payload: schemas.UnitConversionUpdate,
    actor_id: int | None = None,
) -> models.UnitConversion:
    conversion = get_conversion(db, conversion_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(conversion, field, value)
    conversion.updated_by = actor_id
    db.flush()
    return conversion


def soft_delete_conversion(
    db: Session, conversion_id: int, actor_id: int | None = None
) -> models.UnitConversion:
    conversion = get_conversion(db, conversion_id)
    if conversion.is_deleted:
        return conversion
    conversion.is_deleted = True
    conversion.deleted_at = datetime.datetime.now(datetime.UTC)
    conversion.updated_by = actor_id
    db.flush()
    return conversion


def restore_conversion(
    db: Session, conversion_id: int, actor_id: int | None = None
) -> models.UnitConversion:
    conversion = get_conversion(db, conversion_id)
    if not conversion.is_deleted:
        return conversion
    conversion.is_deleted = False
    conversion.deleted_at = None
    conversion.updated_by = actor_id
    db.flush()
    return conversion


# --- Customers -----------------------------------------------------------


def create_customer(
    db: Session, payload: schemas.CustomerCreate, company_id: int, actor_id: int | None = None
) -> models.Customer:
    customer = models.Customer(
        company_id=company_id,
        code=payload.code,
        name_en=payload.name_en,
        name_ar=payload.name_ar,
        customer_type=payload.customer_type,
        payment_terms=payload.payment_terms,
        credit_limit=payload.credit_limit,
        payment_term_days=payload.payment_term_days,
        phone=payload.phone,
        address=payload.address,
        tax_id=payload.tax_id,
        is_active=payload.is_active,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(customer)
    db.flush()
    return customer


def get_customer(db: Session, customer_id: int) -> models.Customer:
    customer = db.get(models.Customer, customer_id)
    if customer is None:
        raise NotFoundError(f"Customer {customer_id} not found")
    return customer


def list_customers(
    db: Session, company_id: int, include_deleted: bool = False
) -> list[models.Customer]:
    stmt = select(models.Customer).where(models.Customer.company_id == company_id)
    if not include_deleted:
        stmt = stmt.where(models.Customer.is_deleted.is_(False))
    return list(db.scalars(stmt.order_by(models.Customer.id)))


def update_customer(
    db: Session, customer_id: int, payload: schemas.CustomerUpdate, actor_id: int | None = None
) -> models.Customer:
    customer = get_customer(db, customer_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    customer.updated_by = actor_id
    db.flush()
    return customer


def soft_delete_customer(
    db: Session, customer_id: int, actor_id: int | None = None
) -> models.Customer:
    customer = get_customer(db, customer_id)
    if customer.is_deleted:
        return customer
    customer.is_deleted = True
    customer.deleted_at = datetime.datetime.now(datetime.UTC)
    customer.updated_by = actor_id
    db.flush()
    return customer


def restore_customer(db: Session, customer_id: int, actor_id: int | None = None) -> models.Customer:
    customer = get_customer(db, customer_id)
    if not customer.is_deleted:
        return customer
    customer.is_deleted = False
    customer.deleted_at = None
    customer.updated_by = actor_id
    db.flush()
    return customer


# --- Suppliers -----------------------------------------------------------


def create_supplier(
    db: Session, payload: schemas.SupplierCreate, company_id: int, actor_id: int | None = None
) -> models.Supplier:
    supplier = models.Supplier(
        company_id=company_id,
        code=payload.code,
        name_en=payload.name_en,
        name_ar=payload.name_ar,
        supplier_type=payload.supplier_type,
        payment_terms=payload.payment_terms,
        phone=payload.phone,
        address=payload.address,
        tax_id=payload.tax_id,
        is_active=payload.is_active,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(supplier)
    db.flush()
    return supplier


def get_supplier(db: Session, supplier_id: int) -> models.Supplier:
    supplier = db.get(models.Supplier, supplier_id)
    if supplier is None:
        raise NotFoundError(f"Supplier {supplier_id} not found")
    return supplier


def list_suppliers(
    db: Session, company_id: int, include_deleted: bool = False
) -> list[models.Supplier]:
    stmt = select(models.Supplier).where(models.Supplier.company_id == company_id)
    if not include_deleted:
        stmt = stmt.where(models.Supplier.is_deleted.is_(False))
    return list(db.scalars(stmt.order_by(models.Supplier.id)))


def update_supplier(
    db: Session, supplier_id: int, payload: schemas.SupplierUpdate, actor_id: int | None = None
) -> models.Supplier:
    supplier = get_supplier(db, supplier_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(supplier, field, value)
    supplier.updated_by = actor_id
    db.flush()
    return supplier


def soft_delete_supplier(
    db: Session, supplier_id: int, actor_id: int | None = None
) -> models.Supplier:
    supplier = get_supplier(db, supplier_id)
    if supplier.is_deleted:
        return supplier
    supplier.is_deleted = True
    supplier.deleted_at = datetime.datetime.now(datetime.UTC)
    supplier.updated_by = actor_id
    db.flush()
    return supplier


def restore_supplier(db: Session, supplier_id: int, actor_id: int | None = None) -> models.Supplier:
    supplier = get_supplier(db, supplier_id)
    if not supplier.is_deleted:
        return supplier
    supplier.is_deleted = False
    supplier.deleted_at = None
    supplier.updated_by = actor_id
    db.flush()
    return supplier
