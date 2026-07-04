from __future__ import annotations

import datetime
import decimal
import enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
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


class MixedTermsPolicy(enum.StrEnum):
    HIGHEST = "HIGHEST"
    LOWEST = "LOWEST"
    SPLIT = "SPLIT"
    REJECT = "REJECT"


class InvoiceStatus(enum.StrEnum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    POSTED = "POSTED"
    COLLECTED = "COLLECTED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class CreditNoteStatus(enum.StrEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    POSTED = "POSTED"
    CANCELLED = "CANCELLED"


class CollectionStatus(enum.StrEnum):
    DRAFT = "DRAFT"
    POSTED = "POSTED"
    CANCELLED = "CANCELLED"


class ApprovalRequestType(enum.StrEnum):
    CREDIT_LIMIT_OVERRIDE = "CREDIT_LIMIT_OVERRIDE"
    NEGATIVE_STOCK = "NEGATIVE_STOCK"
    DISCOUNT_OVERRIDE = "DISCOUNT_OVERRIDE"
    MANUAL_PRICE = "MANUAL_PRICE"
    CANCEL_AFTER_POST = "CANCEL_AFTER_POST"
    BACKDATED_INVOICE = "BACKDATED_INVOICE"


class ApprovalStatus(enum.StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class PriceSource(enum.StrEnum):
    PRICE_LIST = "PRICE_LIST"
    MANUAL = "MANUAL"


class AllocationMethod(enum.StrEnum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"


# ---------------------------------------------------------------------------
# SalesSettings
# ---------------------------------------------------------------------------


class SalesSettings(Base, CompanyScopedMixin, TimestampMixin, AuditMixin):
    __tablename__ = "sales_settings"
    __table_args__ = (
        Index("uq_sales_settings_company", "company_id", unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    mixed_terms_policy: Mapped[MixedTermsPolicy] = mapped_column(
        SAEnum(
            MixedTermsPolicy,
            native_enum=False,
            validate_strings=True,
            length=10,
            name="ck_sales_settings_mixed_terms",
        ),
        nullable=False,
        default=MixedTermsPolicy.HIGHEST,
        server_default="HIGHEST",
    )
    allow_sale_to_inactive_customer: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    allow_sale_over_credit_limit: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    allow_negative_stock_on_sale: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    allow_backdated_invoice: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    next_invoice_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    next_credit_note_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    next_collection_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )


# ---------------------------------------------------------------------------
# PriceList / PriceListItem
# ---------------------------------------------------------------------------


class PriceList(Base, CompanyScopedMixin, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "price_lists"
    __table_args__ = (
        Index(
            "uq_price_lists_company_code",
            "company_id",
            "code",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
        Index(
            "uq_price_lists_company_default",
            "company_id",
            unique=True,
            postgresql_where=text("is_default = true AND is_deleted = false"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name_en: Mapped[str] = mapped_column(String(200), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )


class PriceListItem(Base, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "price_list_items"
    __table_args__ = (
        CheckConstraint("unit_price >= 0", name="ck_price_list_items_price_positive"),
        Index(
            "uq_price_list_items_list_product",
            "price_list_id",
            "product_id",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    price_list_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("price_lists.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    unit_price: Mapped[decimal.Decimal] = mapped_column(Numeric(18, 3), nullable=False)


# ---------------------------------------------------------------------------
# ApprovalRequest
# ---------------------------------------------------------------------------


class ApprovalRequest(Base, CompanyScopedMixin, TimestampMixin, AuditMixin):
    __tablename__ = "approval_requests"
    __table_args__ = (
        Index("ix_approval_requests_ref", "reference_type", "reference_id", "request_type", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    request_type: Mapped[ApprovalRequestType] = mapped_column(
        SAEnum(
            ApprovalRequestType,
            native_enum=False,
            validate_strings=True,
            length=30,
            name="ck_approval_requests_type",
        ),
        nullable=False,
    )
    reference_type: Mapped[str] = mapped_column(String(50), nullable=False)
    reference_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    requested_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ApprovalStatus] = mapped_column(
        SAEnum(
            ApprovalStatus,
            native_enum=False,
            validate_strings=True,
            length=10,
            name="ck_approval_requests_status",
        ),
        nullable=False,
        default=ApprovalStatus.PENDING,
        server_default="PENDING",
    )
    approved_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)


# ---------------------------------------------------------------------------
# SalesInvoice / SalesInvoiceLine
# ---------------------------------------------------------------------------


class SalesInvoice(Base, CompanyScopedMixin, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "sales_invoices"
    __table_args__ = (
        CheckConstraint(
            "due_date IS NULL OR due_date >= invoice_date",
            name="ck_sales_invoices_due_date",
        ),
        Index(
            "uq_sales_invoices_company_number",
            "company_id",
            "invoice_number",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    branch_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    invoice_number: Mapped[str] = mapped_column(String(20), nullable=False)
    customer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    salesman_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    price_list_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("price_lists.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[InvoiceStatus] = mapped_column(
        SAEnum(
            InvoiceStatus,
            native_enum=False,
            validate_strings=True,
            length=20,
            name="ck_sales_invoices_status",
        ),
        nullable=False,
        default=InvoiceStatus.DRAFT,
        server_default="DRAFT",
    )
    payment_terms_type: Mapped[str] = mapped_column(
        String(10),
        CheckConstraint("payment_terms_type IN ('CASH','CREDIT')", name="ck_sales_invoices_payment_terms"),
        nullable=False,
    )
    invoice_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    due_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    posted_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    subtotal: Mapped[decimal.Decimal] = mapped_column(
        Numeric(18, 3), nullable=False, default=0, server_default="0"
    )
    total_discount: Mapped[decimal.Decimal] = mapped_column(
        Numeric(18, 3), nullable=False, default=0, server_default="0"
    )
    total_tax: Mapped[decimal.Decimal] = mapped_column(
        Numeric(18, 3), nullable=False, default=0, server_default="0"
    )
    grand_total: Mapped[decimal.Decimal] = mapped_column(
        Numeric(18, 3), nullable=False, default=0, server_default="0"
    )
    amount_collected: Mapped[decimal.Decimal] = mapped_column(
        Numeric(18, 3), nullable=False, default=0, server_default="0"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class SalesInvoiceLine(Base, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "sales_invoice_lines"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sales_invoices.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    batch_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("batches.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    unit_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("units_of_measure.id", ondelete="RESTRICT"), nullable=False
    )
    quantity_ordered: Mapped[decimal.Decimal] = mapped_column(
        Numeric(18, 6),
        CheckConstraint("quantity_ordered > 0", name="ck_sales_invoice_lines_qty_ordered"),
        nullable=False,
    )
    quantity_delivered: Mapped[decimal.Decimal] = mapped_column(
        Numeric(18, 6),
        CheckConstraint("quantity_delivered > 0", name="ck_sales_invoice_lines_qty_delivered"),
        nullable=False,
    )
    unit_price: Mapped[decimal.Decimal] = mapped_column(
        Numeric(18, 3),
        CheckConstraint("unit_price >= 0", name="ck_sales_invoice_lines_price"),
        nullable=False,
    )
    price_source: Mapped[PriceSource] = mapped_column(
        SAEnum(
            PriceSource,
            native_enum=False,
            validate_strings=True,
            length=12,
            name="ck_sales_invoice_lines_price_source",
        ),
        nullable=False,
    )
    line_discount: Mapped[decimal.Decimal] = mapped_column(
        Numeric(18, 3),
        CheckConstraint("line_discount >= 0", name="ck_sales_invoice_lines_discount"),
        nullable=False,
        default=0,
        server_default="0",
    )
    line_tax: Mapped[decimal.Decimal] = mapped_column(
        Numeric(18, 3),
        CheckConstraint("line_tax >= 0", name="ck_sales_invoice_lines_tax"),
        nullable=False,
        default=0,
        server_default="0",
    )
    line_total: Mapped[decimal.Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    stock_movement_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("stock_movements.id", ondelete="SET NULL"),
        nullable=True,
    )


# ---------------------------------------------------------------------------
# CreditNote / CreditNoteLine
# ---------------------------------------------------------------------------


class CreditNote(Base, CompanyScopedMixin, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "credit_notes"
    __table_args__ = (
        Index(
            "uq_credit_notes_company_number",
            "company_id",
            "credit_note_number",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    branch_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    credit_note_number: Mapped[str] = mapped_column(String(20), nullable=False)
    original_invoice_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sales_invoices.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    customer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[CreditNoteStatus] = mapped_column(
        SAEnum(
            CreditNoteStatus,
            native_enum=False,
            validate_strings=True,
            length=12,
            name="ck_credit_notes_status",
        ),
        nullable=False,
        default=CreditNoteStatus.DRAFT,
        server_default="DRAFT",
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    credit_note_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    subtotal: Mapped[decimal.Decimal] = mapped_column(
        Numeric(18, 3), nullable=False, default=0, server_default="0"
    )
    total_tax: Mapped[decimal.Decimal] = mapped_column(
        Numeric(18, 3), nullable=False, default=0, server_default="0"
    )
    total: Mapped[decimal.Decimal] = mapped_column(
        Numeric(18, 3), nullable=False, default=0, server_default="0"
    )


class CreditNoteLine(Base, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "credit_note_lines"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    credit_note_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("credit_notes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    original_line_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("sales_invoice_lines.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    batch_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("batches.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    unit_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("units_of_measure.id", ondelete="RESTRICT"), nullable=False
    )
    quantity_returned: Mapped[decimal.Decimal] = mapped_column(
        Numeric(18, 6),
        CheckConstraint("quantity_returned > 0", name="ck_credit_note_lines_qty"),
        nullable=False,
    )
    unit_price: Mapped[decimal.Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    line_total: Mapped[decimal.Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    stock_movement_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("stock_movements.id", ondelete="SET NULL"),
        nullable=True,
    )


# ---------------------------------------------------------------------------
# Collection / CollectionLine
# ---------------------------------------------------------------------------


class Collection(Base, CompanyScopedMixin, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "collections"
    __table_args__ = (
        CheckConstraint("total_amount > 0", name="ck_collections_amount_positive"),
        Index(
            "uq_collections_company_number",
            "company_id",
            "collection_number",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    branch_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    collection_number: Mapped[str] = mapped_column(String(20), nullable=False)
    customer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    salesman_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    collection_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[decimal.Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    allocation_method: Mapped[AllocationMethod] = mapped_column(
        SAEnum(
            AllocationMethod,
            native_enum=False,
            validate_strings=True,
            length=6,
            name="ck_collections_allocation",
        ),
        nullable=False,
        default=AllocationMethod.AUTO,
        server_default="AUTO",
    )
    status: Mapped[CollectionStatus] = mapped_column(
        SAEnum(
            CollectionStatus,
            native_enum=False,
            validate_strings=True,
            length=10,
            name="ck_collections_status",
        ),
        nullable=False,
        default=CollectionStatus.DRAFT,
        server_default="DRAFT",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class CollectionLine(Base, TimestampMixin, AuditMixin):
    __tablename__ = "collection_lines"
    __table_args__ = (
        CheckConstraint("amount_allocated > 0", name="ck_collection_lines_amount_positive"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    collection_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("collections.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    invoice_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sales_invoices.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    amount_allocated: Mapped[decimal.Decimal] = mapped_column(Numeric(18, 3), nullable=False)
