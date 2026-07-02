from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import CustomerType, PaymentTerms, ProductType, SupplierType, UnitType

# --- UnitOfMeasure -----------------------------------------------------


class UnitOfMeasureBase(BaseModel):
    code: str = Field(max_length=20)
    name_en: str = Field(max_length=100)
    name_ar: str = Field(max_length=100)
    symbol: str = Field(max_length=10)
    unit_type: UnitType
    is_active: bool = True


class UnitOfMeasureCreate(UnitOfMeasureBase):
    pass


class UnitOfMeasureUpdate(BaseModel):
    # unit_type is deliberately excluded: changing a unit's fundamental nature
    # after conversions/products already reference it would silently break
    # the weight/count invariant everything else relies on.
    code: str | None = Field(default=None, max_length=20)
    name_en: str | None = Field(default=None, max_length=100)
    name_ar: str | None = Field(default=None, max_length=100)
    symbol: str | None = Field(default=None, max_length=10)
    is_active: bool | None = None


class UnitOfMeasureResponse(UnitOfMeasureBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    created_by: int | None
    updated_by: int | None


# --- UnitConversion ------------------------------------------------------


class UnitConversionBase(BaseModel):
    from_unit_id: int
    to_unit_id: int
    factor: Decimal = Field(gt=0)


class UnitConversionCreate(UnitConversionBase):
    product_id: int | None = None  # None = universal, set = product-specific


class UnitConversionUpdate(BaseModel):
    factor: Decimal | None = Field(default=None, gt=0)


class UnitConversionResponse(UnitConversionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    product_id: int | None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    created_by: int | None
    updated_by: int | None


# --- Category --------------------------------------------------------------


class CategoryBase(BaseModel):
    code: str = Field(max_length=20)
    name_en: str = Field(max_length=200)
    name_ar: str = Field(max_length=200)
    parent_id: int | None = None
    is_active: bool = True


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    code: str | None = Field(default=None, max_length=20)
    name_en: str | None = Field(default=None, max_length=200)
    name_ar: str | None = Field(default=None, max_length=200)
    parent_id: int | None = None
    is_active: bool | None = None


class CategoryResponse(CategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    created_by: int | None
    updated_by: int | None


# --- Product -----------------------------------------------------------


class ProductBase(BaseModel):
    code: str = Field(max_length=50)
    name_en: str = Field(max_length=200)
    name_ar: str = Field(max_length=200)
    category_id: int
    product_type: ProductType
    base_unit_id: int
    purchase_unit_id: int | None = None
    sales_unit_id: int | None = None
    barcode: str | None = Field(default=None, max_length=50)
    is_active: bool = True
    is_sellable: bool = True
    is_purchasable: bool = True
    is_stockable: bool = True


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    code: str | None = Field(default=None, max_length=50)
    name_en: str | None = Field(default=None, max_length=200)
    name_ar: str | None = Field(default=None, max_length=200)
    category_id: int | None = None
    product_type: ProductType | None = None
    base_unit_id: int | None = None
    purchase_unit_id: int | None = None
    sales_unit_id: int | None = None
    barcode: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None
    is_sellable: bool | None = None
    is_purchasable: bool | None = None
    is_stockable: bool | None = None


class ProductResponse(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    effective_purchase_unit_id: int
    effective_sales_unit_id: int
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    created_by: int | None
    updated_by: int | None


# --- Customer ------------------------------------------------------------


class CustomerBase(BaseModel):
    code: str = Field(max_length=20)
    name_en: str = Field(max_length=200)
    name_ar: str = Field(max_length=200)
    customer_type: CustomerType
    payment_terms: PaymentTerms
    credit_limit: Decimal | None = Field(default=None, ge=0)
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = None
    tax_id: str | None = Field(default=None, max_length=50)
    is_active: bool = True


class CustomerCreate(CustomerBase):
    @model_validator(mode="after")
    def _credit_limit_requires_credit_terms(self) -> CustomerCreate:
        if self.credit_limit is not None and self.payment_terms != PaymentTerms.CREDIT:
            raise ValueError("credit_limit can only be set when payment_terms is CREDIT")
        return self


class CustomerUpdate(BaseModel):
    code: str | None = Field(default=None, max_length=20)
    name_en: str | None = Field(default=None, max_length=200)
    name_ar: str | None = Field(default=None, max_length=200)
    customer_type: CustomerType | None = None
    payment_terms: PaymentTerms | None = None
    credit_limit: Decimal | None = Field(default=None, ge=0)
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = None
    tax_id: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None


class CustomerResponse(CustomerBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    created_by: int | None
    updated_by: int | None


# --- Supplier ------------------------------------------------------------


class SupplierBase(BaseModel):
    code: str = Field(max_length=20)
    name_en: str = Field(max_length=200)
    name_ar: str = Field(max_length=200)
    supplier_type: SupplierType
    payment_terms: PaymentTerms
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = None
    tax_id: str | None = Field(default=None, max_length=50)
    is_active: bool = True


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    code: str | None = Field(default=None, max_length=20)
    name_en: str | None = Field(default=None, max_length=200)
    name_ar: str | None = Field(default=None, max_length=200)
    supplier_type: SupplierType | None = None
    payment_terms: PaymentTerms | None = None
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = None
    tax_id: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None


class SupplierResponse(SupplierBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    created_by: int | None
    updated_by: int | None
