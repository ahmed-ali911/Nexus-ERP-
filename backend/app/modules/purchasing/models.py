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


class PurchaseFlowPolicy(enum.StrEnum):
    DIRECT_RECEIPT = "DIRECT_RECEIPT"
    PO_REQUIRED = "PO_REQUIRED"
    THREE_WAY_MATCH = "THREE_WAY_MATCH"


class POStatus(enum.StrEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED"
    FULLY_RECEIVED = "FULLY_RECEIVED"
    CANCELLED = "CANCELLED"


class GRNStatus(enum.StrEnum):
    DRAFT = "DRAFT"
    POSTED = "POSTED"
    CANCELLED = "CANCELLED"


class BillStatus(enum.StrEnum):
    DRAFT = "DRAFT"
    POSTED = "POSTED"
    PAID = "PAID"
    CANCELLED = "CANCELLED"


class ReturnStatus(enum.StrEnum):
    DRAFT = "DRAFT"
    POSTED = "POSTED"


class PaymentStatus(enum.StrEnum):
    DRAFT = "DRAFT"
    POSTED = "POSTED"
    CANCELLED = "CANCELLED"


class PaymentAllocationMethod(enum.StrEnum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"


# ---------------------------------------------------------------------------
# PurchaseSettings
# ---------------------------------------------------------------------------


class PurchaseSettings(Base, CompanyScopedMixin, TimestampMixin, AuditMixin):
    __tablename__ = "purchase_settings"
    __table_args__ = (
        Index("uq_purchase_settings_company", "company_id", unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    purchase_flow_policy: Mapped[PurchaseFlowPolicy] = mapped_column(
        SAEnum(
            PurchaseFlowPolicy,
            native_enum=False,
            validate_strings=True,
            length=20,
            name="ck_purchase_settings_flow_policy",
        ),
        nullable=False,
        default=PurchaseFlowPolicy.DIRECT_RECEIPT,
        server_default="DIRECT_RECEIPT",
    )
    allow_supplier_over_credit_limit: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    allow_backdated_purchase_docs: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    max_price_variance_pct: Mapped[decimal.Decimal] = mapped_column(
        Numeric(5, 2),
        CheckConstraint(
            "max_price_variance_pct >= 0 AND max_price_variance_pct <= 100",
            name="ck_purchase_settings_variance_pct",
        ),
        nullable=False,
        default=0,
        server_default="0.00",
    )
    next_po_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    next_grn_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    next_bill_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    next_payment_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    next_return_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )


# ---------------------------------------------------------------------------
# PurchaseOrder / PurchaseOrderLine
# ---------------------------------------------------------------------------


class PurchaseOrder(Base, CompanyScopedMixin, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        Index(
            "uq_purchase_orders_company_number",
            "company_id",
            "po_number",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    branch_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    supplier_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    po_number: Mapped[str] = mapped_column(String(30), nullable=False)
    po_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    status: Mapped[POStatus] = mapped_column(
        SAEnum(
            POStatus,
            native_enum=False,
            validate_strings=True,
            length=20,
            name="ck_purchase_orders_status",
        ),
        nullable=False,
        default=POStatus.DRAFT,
        server_default="DRAFT",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class PurchaseOrderLine(Base, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "purchase_order_lines"
    __table_args__ = (
        CheckConstraint("quantity_ordered > 0", name="ck_po_lines_qty_positive"),
        CheckConstraint("unit_cost >= 0", name="ck_po_lines_cost_nonneg"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    po_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("purchase_orders.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    unit_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("units_of_measure.id", ondelete="RESTRICT"), nullable=False
    )
    quantity_ordered: Mapped[decimal.Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    quantity_received: Mapped[decimal.Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=0, server_default="0"
    )
    unit_cost: Mapped[decimal.Decimal] = mapped_column(Numeric(18, 3), nullable=False)


# ---------------------------------------------------------------------------
# GoodsReceipt / GoodsReceiptLine
# ---------------------------------------------------------------------------


class GoodsReceipt(Base, CompanyScopedMixin, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "goods_receipts"
    __table_args__ = (
        Index(
            "uq_goods_receipts_company_number",
            "company_id",
            "grn_number",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    branch_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    supplier_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    purchase_order_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("purchase_orders.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    grn_number: Mapped[str] = mapped_column(String(30), nullable=False)
    receipt_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    status: Mapped[GRNStatus] = mapped_column(
        SAEnum(
            GRNStatus,
            native_enum=False,
            validate_strings=True,
            length=12,
            name="ck_goods_receipts_status",
        ),
        nullable=False,
        default=GRNStatus.DRAFT,
        server_default="DRAFT",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class GoodsReceiptLine(Base, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "goods_receipt_lines"
    __table_args__ = (
        CheckConstraint("quantity_received > 0", name="ck_grn_lines_qty_positive"),
        CheckConstraint("unit_cost >= 0", name="ck_grn_lines_cost_nonneg"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    grn_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("goods_receipts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    po_line_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("purchase_order_lines.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    unit_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("units_of_measure.id", ondelete="RESTRICT"), nullable=False
    )
    quantity_received: Mapped[decimal.Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit_cost: Mapped[decimal.Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    batch_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("batches.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    batch_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    expiry_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    stock_movement_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("stock_movements.id", ondelete="SET NULL"), nullable=True
    )


# ---------------------------------------------------------------------------
# SupplierInvoice / SupplierInvoiceLine
# ---------------------------------------------------------------------------


class SupplierInvoice(Base, CompanyScopedMixin, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "supplier_invoices"
    __table_args__ = (
        CheckConstraint(
            "due_date IS NULL OR due_date >= bill_date",
            name="ck_supplier_invoices_due_date",
        ),
        Index(
            "uq_supplier_invoices_company_number",
            "company_id",
            "bill_number",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    branch_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    supplier_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    goods_receipt_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("goods_receipts.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    purchase_order_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("purchase_orders.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    bill_number: Mapped[str] = mapped_column(String(30), nullable=False)
    supplier_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bill_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    due_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    status: Mapped[BillStatus] = mapped_column(
        SAEnum(
            BillStatus,
            native_enum=False,
            validate_strings=True,
            length=12,
            name="ck_supplier_invoices_status",
        ),
        nullable=False,
        default=BillStatus.DRAFT,
        server_default="DRAFT",
    )
    grand_total: Mapped[decimal.Decimal] = mapped_column(
        Numeric(18, 3), nullable=False, default=0, server_default="0"
    )
    amount_paid: Mapped[decimal.Decimal] = mapped_column(
        Numeric(18, 3), nullable=False, default=0, server_default="0"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    posted_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class SupplierInvoiceLine(Base, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "supplier_invoice_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_supplier_invoice_lines_qty_positive"),
        CheckConstraint("unit_cost >= 0", name="ck_supplier_invoice_lines_cost_nonneg"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    bill_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("supplier_invoices.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    grn_line_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("goods_receipt_lines.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    unit_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("units_of_measure.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[decimal.Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit_cost: Mapped[decimal.Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    # LANDED COST EXTENSION POINT:
    # cost_adjustment → grn_line_id → GoodsReceiptLine.stock_movement_id → StockMovement
    # When landed cost is implemented, apply_cost_adjustment(bill_id) follows this chain
    # to revalue the WAC of received stock.
    cost_adjustment: Mapped[decimal.Decimal] = mapped_column(
        Numeric(18, 3), nullable=False, default=0, server_default="0.000"
    )
    line_total: Mapped[decimal.Decimal] = mapped_column(Numeric(18, 3), nullable=False)


# ---------------------------------------------------------------------------
# PurchaseReturn / PurchaseReturnLine
# ---------------------------------------------------------------------------


class PurchaseReturn(Base, CompanyScopedMixin, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "purchase_returns"
    __table_args__ = (
        Index(
            "uq_purchase_returns_company_number",
            "company_id",
            "return_number",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    branch_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    supplier_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    original_grn_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("goods_receipts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    return_number: Mapped[str] = mapped_column(String(30), nullable=False)
    return_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    status: Mapped[ReturnStatus] = mapped_column(
        SAEnum(
            ReturnStatus,
            native_enum=False,
            validate_strings=True,
            length=8,
            name="ck_purchase_returns_status",
        ),
        nullable=False,
        default=ReturnStatus.DRAFT,
        server_default="DRAFT",
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    total: Mapped[decimal.Decimal] = mapped_column(
        Numeric(18, 3), nullable=False, default=0, server_default="0"
    )


class PurchaseReturnLine(Base, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "purchase_return_lines"
    __table_args__ = (
        CheckConstraint("quantity_returned > 0", name="ck_pr_lines_qty_positive"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    return_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("purchase_returns.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    original_grn_line_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("goods_receipt_lines.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity_returned: Mapped[decimal.Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    line_total: Mapped[decimal.Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    stock_movement_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("stock_movements.id", ondelete="SET NULL"), nullable=True
    )


# ---------------------------------------------------------------------------
# SupplierPayment / SupplierPaymentLine
# ---------------------------------------------------------------------------


class SupplierPayment(Base, CompanyScopedMixin, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "supplier_payments"
    __table_args__ = (
        CheckConstraint("total_amount > 0", name="ck_supplier_payments_amount_positive"),
        Index(
            "uq_supplier_payments_company_number",
            "company_id",
            "payment_number",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    branch_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    supplier_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    payment_number: Mapped[str] = mapped_column(String(30), nullable=False)
    payment_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[decimal.Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    allocation_method: Mapped[PaymentAllocationMethod] = mapped_column(
        SAEnum(
            PaymentAllocationMethod,
            native_enum=False,
            validate_strings=True,
            length=6,
            name="ck_supplier_payments_allocation",
        ),
        nullable=False,
        default=PaymentAllocationMethod.AUTO,
        server_default="AUTO",
    )
    status: Mapped[PaymentStatus] = mapped_column(
        SAEnum(
            PaymentStatus,
            native_enum=False,
            validate_strings=True,
            length=10,
            name="ck_supplier_payments_status",
        ),
        nullable=False,
        default=PaymentStatus.DRAFT,
        server_default="DRAFT",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class SupplierPaymentLine(Base, TimestampMixin, AuditMixin):
    __tablename__ = "supplier_payment_lines"
    __table_args__ = (
        CheckConstraint("amount_applied > 0", name="ck_supplier_payment_lines_amount_positive"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    payment_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("supplier_payments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    bill_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("supplier_invoices.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount_applied: Mapped[decimal.Decimal] = mapped_column(Numeric(18, 3), nullable=False)
