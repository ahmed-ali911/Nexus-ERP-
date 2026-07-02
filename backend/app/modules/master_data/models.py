from __future__ import annotations

import decimal
import enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.mixins import AuditMixin, SoftDeleteMixin, TimestampMixin
from app.modules.organization.mixins import CompanyScopedMixin


class UnitType(enum.StrEnum):
    WEIGHT = "WEIGHT"
    COUNT = "COUNT"
    VOLUME = "VOLUME"


class ProductType(enum.StrEnum):
    RAW_MATERIAL = "RAW_MATERIAL"
    SEMI_FINISHED = "SEMI_FINISHED"
    FINISHED_GOOD = "FINISHED_GOOD"


class CustomerType(enum.StrEnum):
    COMPANY = "COMPANY"
    SHOP = "SHOP"
    MARKET = "MARKET"
    INDIVIDUAL = "INDIVIDUAL"


class PaymentTerms(enum.StrEnum):
    CASH = "CASH"
    CREDIT = "CREDIT"


class SupplierType(enum.StrEnum):
    LOCAL = "LOCAL"
    IMPORT = "IMPORT"


class UnitOfMeasure(Base, CompanyScopedMixin, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "units_of_measure"
    __table_args__ = (
        Index(
            "uq_units_of_measure_company_code",
            "company_id",
            "code",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name_en: Mapped[str] = mapped_column(String(100), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    unit_type: Mapped[UnitType] = mapped_column(
        SAEnum(
            UnitType,
            native_enum=False,
            validate_strings=True,
            length=20,
            name="ck_units_of_measure_unit_type",
        ),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )


class Category(Base, CompanyScopedMixin, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "categories"
    __table_args__ = (
        Index(
            "uq_categories_company_code",
            "company_id",
            "code",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name_en: Mapped[str] = mapped_column(String(200), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("categories.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )


class Product(Base, CompanyScopedMixin, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "products"
    __table_args__ = (
        Index(
            "uq_products_company_code",
            "company_id",
            "code",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
        Index(
            "uq_products_company_barcode",
            "company_id",
            "barcode",
            unique=True,
            postgresql_where=text("is_deleted = false AND barcode IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name_en: Mapped[str] = mapped_column(String(200), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    category_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    product_type: Mapped[ProductType] = mapped_column(
        SAEnum(
            ProductType,
            native_enum=False,
            validate_strings=True,
            length=20,
            name="ck_products_product_type",
        ),
        nullable=False,
    )
    base_unit_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("units_of_measure.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    purchase_unit_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("units_of_measure.id", ondelete="RESTRICT"), nullable=True
    )
    sales_unit_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("units_of_measure.id", ondelete="RESTRICT"), nullable=True
    )
    barcode: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    is_sellable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    is_purchasable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    is_stockable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    @property
    def effective_purchase_unit_id(self) -> int:
        return self.purchase_unit_id or self.base_unit_id

    @property
    def effective_sales_unit_id(self) -> int:
        return self.sales_unit_id or self.base_unit_id


class UnitConversion(Base, CompanyScopedMixin, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "unit_conversions"
    __table_args__ = (
        CheckConstraint("from_unit_id <> to_unit_id", name="ck_unit_conversions_distinct_units"),
        CheckConstraint("factor > 0", name="ck_unit_conversions_factor_positive"),
        # product_id IS NULL => universal rule for this unit pair (company-wide).
        # product_id set => override specific to that product.
        Index(
            "uq_unit_conversions_universal",
            "company_id",
            "from_unit_id",
            "to_unit_id",
            unique=True,
            postgresql_where=text("product_id IS NULL AND is_deleted = false"),
        ),
        Index(
            "uq_unit_conversions_product_specific",
            "company_id",
            "product_id",
            "from_unit_id",
            "to_unit_id",
            unique=True,
            postgresql_where=text("product_id IS NOT NULL AND is_deleted = false"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    product_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    from_unit_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("units_of_measure.id", ondelete="RESTRICT"), nullable=False
    )
    to_unit_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("units_of_measure.id", ondelete="RESTRICT"), nullable=False
    )
    factor: Mapped[decimal.Decimal] = mapped_column(Numeric(18, 6), nullable=False)


class Customer(Base, CompanyScopedMixin, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "customers"
    __table_args__ = (
        Index(
            "uq_customers_company_code",
            "company_id",
            "code",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
        CheckConstraint(
            "payment_terms = 'CREDIT' OR credit_limit IS NULL",
            name="ck_customers_credit_limit_requires_credit_terms",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name_en: Mapped[str] = mapped_column(String(200), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    customer_type: Mapped[CustomerType] = mapped_column(
        SAEnum(
            CustomerType,
            native_enum=False,
            validate_strings=True,
            length=20,
            name="ck_customers_customer_type",
        ),
        nullable=False,
    )
    payment_terms: Mapped[PaymentTerms] = mapped_column(
        SAEnum(
            PaymentTerms,
            native_enum=False,
            validate_strings=True,
            length=20,
            name="ck_customers_payment_terms",
        ),
        nullable=False,
    )
    credit_limit: Mapped[decimal.Decimal | None] = mapped_column(Numeric(18, 3), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )


class Supplier(Base, CompanyScopedMixin, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "suppliers"
    __table_args__ = (
        Index(
            "uq_suppliers_company_code",
            "company_id",
            "code",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name_en: Mapped[str] = mapped_column(String(200), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    supplier_type: Mapped[SupplierType] = mapped_column(
        SAEnum(
            SupplierType,
            native_enum=False,
            validate_strings=True,
            length=20,
            name="ck_suppliers_supplier_type",
        ),
        nullable=False,
    )
    payment_terms: Mapped[PaymentTerms] = mapped_column(
        SAEnum(
            PaymentTerms,
            native_enum=False,
            validate_strings=True,
            length=20,
            name="ck_suppliers_payment_terms",
        ),
        nullable=False,
    )
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
