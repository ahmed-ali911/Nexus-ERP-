from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import require_permission
from app.modules.auth.models import User

from . import schemas, service

router = APIRouter(prefix="/master-data", tags=["master-data"])

# --- Units of Measure ------------------------------------------------------


@router.post("/units", response_model=schemas.UnitOfMeasureResponse, status_code=201)
def create_unit(
    payload: schemas.UnitOfMeasureCreate,
    current_user: User = Depends(require_permission("master_data.unit.create")),
    db: Session = Depends(get_db),
):
    return service.create_unit(
        db, payload, company_id=current_user.company_id, actor_id=current_user.id
    )


@router.get("/units", response_model=list[schemas.UnitOfMeasureResponse])
def list_units(
    include_deleted: bool = False,
    current_user: User = Depends(require_permission("master_data.unit.read")),
    db: Session = Depends(get_db),
):
    return service.list_units(
        db, company_id=current_user.company_id, include_deleted=include_deleted
    )


@router.get("/units/{unit_id}", response_model=schemas.UnitOfMeasureResponse)
def get_unit(
    unit_id: int,
    current_user: User = Depends(require_permission("master_data.unit.read")),
    db: Session = Depends(get_db),
):
    return service.get_unit(db, unit_id)


@router.patch("/units/{unit_id}", response_model=schemas.UnitOfMeasureResponse)
def update_unit(
    unit_id: int,
    payload: schemas.UnitOfMeasureUpdate,
    current_user: User = Depends(require_permission("master_data.unit.update")),
    db: Session = Depends(get_db),
):
    return service.update_unit(db, unit_id, payload, actor_id=current_user.id)


@router.delete("/units/{unit_id}", response_model=schemas.UnitOfMeasureResponse)
def delete_unit(
    unit_id: int,
    current_user: User = Depends(require_permission("master_data.unit.delete")),
    db: Session = Depends(get_db),
):
    return service.soft_delete_unit(db, unit_id, actor_id=current_user.id)


@router.post("/units/{unit_id}/restore", response_model=schemas.UnitOfMeasureResponse)
def restore_unit(
    unit_id: int,
    current_user: User = Depends(require_permission("master_data.unit.restore")),
    db: Session = Depends(get_db),
):
    return service.restore_unit(db, unit_id, actor_id=current_user.id)


# --- Categories --------------------------------------------------------


@router.post("/categories", response_model=schemas.CategoryResponse, status_code=201)
def create_category(
    payload: schemas.CategoryCreate,
    current_user: User = Depends(require_permission("master_data.category.create")),
    db: Session = Depends(get_db),
):
    return service.create_category(
        db, payload, company_id=current_user.company_id, actor_id=current_user.id
    )


@router.get("/categories", response_model=list[schemas.CategoryResponse])
def list_categories(
    include_deleted: bool = False,
    current_user: User = Depends(require_permission("master_data.category.read")),
    db: Session = Depends(get_db),
):
    return service.list_categories(
        db, company_id=current_user.company_id, include_deleted=include_deleted
    )


@router.get("/categories/{category_id}", response_model=schemas.CategoryResponse)
def get_category(
    category_id: int,
    current_user: User = Depends(require_permission("master_data.category.read")),
    db: Session = Depends(get_db),
):
    return service.get_category(db, category_id)


@router.patch("/categories/{category_id}", response_model=schemas.CategoryResponse)
def update_category(
    category_id: int,
    payload: schemas.CategoryUpdate,
    current_user: User = Depends(require_permission("master_data.category.update")),
    db: Session = Depends(get_db),
):
    return service.update_category(db, category_id, payload, actor_id=current_user.id)


@router.delete("/categories/{category_id}", response_model=schemas.CategoryResponse)
def delete_category(
    category_id: int,
    current_user: User = Depends(require_permission("master_data.category.delete")),
    db: Session = Depends(get_db),
):
    return service.soft_delete_category(db, category_id, actor_id=current_user.id)


@router.post("/categories/{category_id}/restore", response_model=schemas.CategoryResponse)
def restore_category(
    category_id: int,
    current_user: User = Depends(require_permission("master_data.category.restore")),
    db: Session = Depends(get_db),
):
    return service.restore_category(db, category_id, actor_id=current_user.id)


# --- Products ------------------------------------------------------------


@router.post("/products", response_model=schemas.ProductResponse, status_code=201)
def create_product(
    payload: schemas.ProductCreate,
    current_user: User = Depends(require_permission("master_data.product.create")),
    db: Session = Depends(get_db),
):
    return service.create_product(
        db, payload, company_id=current_user.company_id, actor_id=current_user.id
    )


@router.get("/products", response_model=list[schemas.ProductResponse])
def list_products(
    category_id: int | None = None,
    include_deleted: bool = False,
    current_user: User = Depends(require_permission("master_data.product.read")),
    db: Session = Depends(get_db),
):
    return service.list_products(
        db,
        company_id=current_user.company_id,
        category_id=category_id,
        include_deleted=include_deleted,
    )


@router.get("/products/{product_id}", response_model=schemas.ProductResponse)
def get_product(
    product_id: int,
    current_user: User = Depends(require_permission("master_data.product.read")),
    db: Session = Depends(get_db),
):
    return service.get_product(db, product_id)


@router.patch("/products/{product_id}", response_model=schemas.ProductResponse)
def update_product(
    product_id: int,
    payload: schemas.ProductUpdate,
    current_user: User = Depends(require_permission("master_data.product.update")),
    db: Session = Depends(get_db),
):
    return service.update_product(db, product_id, payload, actor_id=current_user.id)


@router.delete("/products/{product_id}", response_model=schemas.ProductResponse)
def delete_product(
    product_id: int,
    current_user: User = Depends(require_permission("master_data.product.delete")),
    db: Session = Depends(get_db),
):
    return service.soft_delete_product(db, product_id, actor_id=current_user.id)


@router.post("/products/{product_id}/restore", response_model=schemas.ProductResponse)
def restore_product(
    product_id: int,
    current_user: User = Depends(require_permission("master_data.product.restore")),
    db: Session = Depends(get_db),
):
    return service.restore_product(db, product_id, actor_id=current_user.id)


# --- Unit Conversions --------------------------------------------------


@router.post("/conversions", response_model=schemas.UnitConversionResponse, status_code=201)
def create_conversion(
    payload: schemas.UnitConversionCreate,
    current_user: User = Depends(require_permission("master_data.conversion.create")),
    db: Session = Depends(get_db),
):
    return service.create_conversion(
        db, payload, company_id=current_user.company_id, actor_id=current_user.id
    )


@router.get("/conversions", response_model=list[schemas.UnitConversionResponse])
def list_conversions(
    product_id: int | None = None,
    include_deleted: bool = False,
    current_user: User = Depends(require_permission("master_data.conversion.read")),
    db: Session = Depends(get_db),
):
    return service.list_conversions(
        db,
        company_id=current_user.company_id,
        product_id=product_id,
        include_deleted=include_deleted,
    )


@router.get("/conversions/{conversion_id}", response_model=schemas.UnitConversionResponse)
def get_conversion(
    conversion_id: int,
    current_user: User = Depends(require_permission("master_data.conversion.read")),
    db: Session = Depends(get_db),
):
    return service.get_conversion(db, conversion_id)


@router.patch("/conversions/{conversion_id}", response_model=schemas.UnitConversionResponse)
def update_conversion(
    conversion_id: int,
    payload: schemas.UnitConversionUpdate,
    current_user: User = Depends(require_permission("master_data.conversion.update")),
    db: Session = Depends(get_db),
):
    return service.update_conversion(db, conversion_id, payload, actor_id=current_user.id)


@router.delete("/conversions/{conversion_id}", response_model=schemas.UnitConversionResponse)
def delete_conversion(
    conversion_id: int,
    current_user: User = Depends(require_permission("master_data.conversion.delete")),
    db: Session = Depends(get_db),
):
    return service.soft_delete_conversion(db, conversion_id, actor_id=current_user.id)


@router.post("/conversions/{conversion_id}/restore", response_model=schemas.UnitConversionResponse)
def restore_conversion(
    conversion_id: int,
    current_user: User = Depends(require_permission("master_data.conversion.restore")),
    db: Session = Depends(get_db),
):
    return service.restore_conversion(db, conversion_id, actor_id=current_user.id)


# --- Customers -----------------------------------------------------------


@router.post("/customers", response_model=schemas.CustomerResponse, status_code=201)
def create_customer(
    payload: schemas.CustomerCreate,
    current_user: User = Depends(require_permission("master_data.customer.create")),
    db: Session = Depends(get_db),
):
    return service.create_customer(
        db, payload, company_id=current_user.company_id, actor_id=current_user.id
    )


@router.get("/customers", response_model=list[schemas.CustomerResponse])
def list_customers(
    include_deleted: bool = False,
    current_user: User = Depends(require_permission("master_data.customer.read")),
    db: Session = Depends(get_db),
):
    return service.list_customers(
        db, company_id=current_user.company_id, include_deleted=include_deleted
    )


@router.get("/customers/{customer_id}", response_model=schemas.CustomerResponse)
def get_customer(
    customer_id: int,
    current_user: User = Depends(require_permission("master_data.customer.read")),
    db: Session = Depends(get_db),
):
    return service.get_customer(db, customer_id)


@router.patch("/customers/{customer_id}", response_model=schemas.CustomerResponse)
def update_customer(
    customer_id: int,
    payload: schemas.CustomerUpdate,
    current_user: User = Depends(require_permission("master_data.customer.update")),
    db: Session = Depends(get_db),
):
    return service.update_customer(db, customer_id, payload, actor_id=current_user.id)


@router.delete("/customers/{customer_id}", response_model=schemas.CustomerResponse)
def delete_customer(
    customer_id: int,
    current_user: User = Depends(require_permission("master_data.customer.delete")),
    db: Session = Depends(get_db),
):
    return service.soft_delete_customer(db, customer_id, actor_id=current_user.id)


@router.post("/customers/{customer_id}/restore", response_model=schemas.CustomerResponse)
def restore_customer(
    customer_id: int,
    current_user: User = Depends(require_permission("master_data.customer.restore")),
    db: Session = Depends(get_db),
):
    return service.restore_customer(db, customer_id, actor_id=current_user.id)


# --- Suppliers -----------------------------------------------------------


@router.post("/suppliers", response_model=schemas.SupplierResponse, status_code=201)
def create_supplier(
    payload: schemas.SupplierCreate,
    current_user: User = Depends(require_permission("master_data.supplier.create")),
    db: Session = Depends(get_db),
):
    return service.create_supplier(
        db, payload, company_id=current_user.company_id, actor_id=current_user.id
    )


@router.get("/suppliers", response_model=list[schemas.SupplierResponse])
def list_suppliers(
    include_deleted: bool = False,
    current_user: User = Depends(require_permission("master_data.supplier.read")),
    db: Session = Depends(get_db),
):
    return service.list_suppliers(
        db, company_id=current_user.company_id, include_deleted=include_deleted
    )


@router.get("/suppliers/{supplier_id}", response_model=schemas.SupplierResponse)
def get_supplier(
    supplier_id: int,
    current_user: User = Depends(require_permission("master_data.supplier.read")),
    db: Session = Depends(get_db),
):
    return service.get_supplier(db, supplier_id)


@router.patch("/suppliers/{supplier_id}", response_model=schemas.SupplierResponse)
def update_supplier(
    supplier_id: int,
    payload: schemas.SupplierUpdate,
    current_user: User = Depends(require_permission("master_data.supplier.update")),
    db: Session = Depends(get_db),
):
    return service.update_supplier(db, supplier_id, payload, actor_id=current_user.id)


@router.delete("/suppliers/{supplier_id}", response_model=schemas.SupplierResponse)
def delete_supplier(
    supplier_id: int,
    current_user: User = Depends(require_permission("master_data.supplier.delete")),
    db: Session = Depends(get_db),
):
    return service.soft_delete_supplier(db, supplier_id, actor_id=current_user.id)


@router.post("/suppliers/{supplier_id}/restore", response_model=schemas.SupplierResponse)
def restore_supplier(
    supplier_id: int,
    current_user: User = Depends(require_permission("master_data.supplier.restore")),
    db: Session = Depends(get_db),
):
    return service.restore_supplier(db, supplier_id, actor_id=current_user.id)
