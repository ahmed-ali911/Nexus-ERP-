from __future__ import annotations

import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from .models import (
    BillStatus,
    GRNStatus,
    POStatus,
    PaymentAllocationMethod,
    PaymentStatus,
    PurchaseFlowPolicy,
    ReturnStatus,
)


# --- PurchaseSettings -------------------------------------------------------


class PurchaseSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    purchase_flow_policy: PurchaseFlowPolicy
    allow_supplier_over_credit_limit: bool
    allow_backdated_purchase_docs: bool
    max_price_variance_pct: Decimal
    next_po_number: int
    next_grn_number: int
    next_bill_number: int
    next_payment_number: int
    next_return_number: int


class PurchaseSettingsUpdate(BaseModel):
    purchase_flow_policy: PurchaseFlowPolicy | None = None
    allow_supplier_over_credit_limit: bool | None = None
    allow_backdated_purchase_docs: bool | None = None
    max_price_variance_pct: Decimal | None = Field(default=None, ge=0, le=100)


# --- PurchaseOrder ----------------------------------------------------------


class POLineCreate(BaseModel):
    product_id: int
    unit_id: int
    quantity_ordered: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(ge=0)


class POLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    po_id: int
    product_id: int
    unit_id: int
    quantity_ordered: Decimal
    quantity_received: Decimal
    unit_cost: Decimal
    is_deleted: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime
    created_by: int | None
    updated_by: int | None


class PurchaseOrderCreate(BaseModel):
    branch_id: int
    supplier_id: int
    po_date: datetime.date
    notes: str | None = None
    lines: list[POLineCreate] = Field(min_length=1)


class PurchaseOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    branch_id: int
    supplier_id: int
    po_number: str
    po_date: datetime.date
    status: POStatus
    notes: str | None
    is_deleted: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime
    created_by: int | None
    updated_by: int | None


class PurchaseOrderDetailResponse(PurchaseOrderResponse):
    lines: list[POLineResponse] = []


class CancelPOPayload(BaseModel):
    reason: str | None = None


# --- GoodsReceipt -----------------------------------------------------------


class GRNLineCreate(BaseModel):
    po_line_id: int | None = None
    product_id: int
    warehouse_id: int
    unit_id: int
    quantity_received: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(ge=0)
    batch_id: int | None = None
    batch_number: str | None = Field(default=None, max_length=100)
    expiry_date: datetime.date | None = None


class GRNLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    grn_id: int
    po_line_id: int | None
    product_id: int
    warehouse_id: int
    unit_id: int
    quantity_received: Decimal
    unit_cost: Decimal
    batch_id: int | None
    batch_number: str | None
    expiry_date: datetime.date | None
    stock_movement_id: int | None
    is_deleted: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime
    created_by: int | None
    updated_by: int | None


class GoodsReceiptCreate(BaseModel):
    branch_id: int
    supplier_id: int
    purchase_order_id: int | None = None
    receipt_date: datetime.date
    notes: str | None = None
    lines: list[GRNLineCreate] = Field(min_length=1)


class GoodsReceiptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    branch_id: int
    supplier_id: int
    purchase_order_id: int | None
    grn_number: str
    receipt_date: datetime.date
    status: GRNStatus
    notes: str | None
    is_deleted: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime
    created_by: int | None
    updated_by: int | None


class GoodsReceiptDetailResponse(GoodsReceiptResponse):
    lines: list[GRNLineResponse] = []


class CancelGRNPayload(BaseModel):
    reason: str | None = None


# --- SupplierInvoice --------------------------------------------------------


class BillLineCreate(BaseModel):
    grn_line_id: int | None = None
    product_id: int
    unit_id: int
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(ge=0)
    cost_adjustment: Decimal = Field(default=Decimal(0), ge=0)


class BillLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    bill_id: int
    grn_line_id: int | None
    product_id: int
    unit_id: int
    quantity: Decimal
    unit_cost: Decimal
    cost_adjustment: Decimal
    line_total: Decimal
    is_deleted: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime
    created_by: int | None
    updated_by: int | None


class SupplierInvoiceCreate(BaseModel):
    branch_id: int
    supplier_id: int
    goods_receipt_id: int | None = None
    purchase_order_id: int | None = None
    supplier_ref: str | None = None
    bill_date: datetime.date
    notes: str | None = None
    lines: list[BillLineCreate] = Field(min_length=1)


class SupplierInvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    branch_id: int
    supplier_id: int
    goods_receipt_id: int | None
    purchase_order_id: int | None
    bill_number: str
    supplier_ref: str | None
    bill_date: datetime.date
    due_date: datetime.date | None
    status: BillStatus
    grand_total: Decimal
    amount_paid: Decimal
    notes: str | None
    posted_at: datetime.datetime | None
    is_deleted: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime
    created_by: int | None
    updated_by: int | None


class SupplierInvoiceDetailResponse(SupplierInvoiceResponse):
    lines: list[BillLineResponse] = []


class CancelBillPayload(BaseModel):
    reason: str | None = None


# --- PurchaseReturn ---------------------------------------------------------


class ReturnLineCreate(BaseModel):
    original_grn_line_id: int
    quantity_returned: Decimal = Field(gt=0)


class ReturnLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    return_id: int
    original_grn_line_id: int
    quantity_returned: Decimal
    line_total: Decimal
    stock_movement_id: int | None
    is_deleted: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime
    created_by: int | None
    updated_by: int | None


class PurchaseReturnCreate(BaseModel):
    branch_id: int
    supplier_id: int
    original_grn_id: int
    return_date: datetime.date
    reason: str | None = None
    lines: list[ReturnLineCreate] = Field(min_length=1)


class PurchaseReturnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    branch_id: int
    supplier_id: int
    original_grn_id: int
    return_number: str
    return_date: datetime.date
    status: ReturnStatus
    reason: str | None
    total: Decimal
    is_deleted: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime
    created_by: int | None
    updated_by: int | None


class PurchaseReturnDetailResponse(PurchaseReturnResponse):
    lines: list[ReturnLineResponse] = []


# --- SupplierPayment --------------------------------------------------------


class PaymentLineCreate(BaseModel):
    bill_id: int
    amount_applied: Decimal = Field(gt=0)


class PaymentLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    payment_id: int
    bill_id: int
    amount_applied: Decimal
    created_at: datetime.datetime
    updated_at: datetime.datetime
    created_by: int | None
    updated_by: int | None


class SupplierPaymentCreate(BaseModel):
    branch_id: int
    supplier_id: int
    payment_date: datetime.date
    total_amount: Decimal = Field(gt=0)
    allocation_method: PaymentAllocationMethod = PaymentAllocationMethod.AUTO
    notes: str | None = None
    lines: list[PaymentLineCreate] = []


class SupplierPaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    branch_id: int
    supplier_id: int
    payment_number: str
    payment_date: datetime.date
    total_amount: Decimal
    allocation_method: PaymentAllocationMethod
    status: PaymentStatus
    notes: str | None
    is_deleted: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime
    created_by: int | None
    updated_by: int | None


class SupplierPaymentDetailResponse(SupplierPaymentResponse):
    lines: list[PaymentLineResponse] = []
