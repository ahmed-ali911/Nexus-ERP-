from __future__ import annotations

import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from .models import (
    AllocationMethod,
    ApprovalRequestType,
    ApprovalStatus,
    CollectionStatus,
    CreditNoteStatus,
    InvoiceStatus,
    MixedTermsPolicy,
    PriceSource,
)

# --- SalesSettings ----------------------------------------------------------


class SalesSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    mixed_terms_policy: MixedTermsPolicy
    allow_sale_to_inactive_customer: bool
    allow_sale_over_credit_limit: bool
    allow_negative_stock_on_sale: bool
    allow_backdated_invoice: bool
    next_invoice_number: int
    next_credit_note_number: int
    next_collection_number: int


class SalesSettingsUpdate(BaseModel):
    mixed_terms_policy: MixedTermsPolicy | None = None
    allow_sale_to_inactive_customer: bool | None = None
    allow_sale_over_credit_limit: bool | None = None
    allow_negative_stock_on_sale: bool | None = None
    allow_backdated_invoice: bool | None = None


# --- PriceList --------------------------------------------------------------


class PriceListCreate(BaseModel):
    code: str = Field(max_length=20)
    name_en: str = Field(max_length=200)
    name_ar: str = Field(max_length=200)
    is_default: bool = False
    is_active: bool = True


class PriceListUpdate(BaseModel):
    name_en: str | None = Field(default=None, max_length=200)
    name_ar: str | None = Field(default=None, max_length=200)
    is_default: bool | None = None
    is_active: bool | None = None


class PriceListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    code: str
    name_en: str
    name_ar: str
    is_default: bool
    is_active: bool
    is_deleted: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime
    created_by: int | None
    updated_by: int | None


# --- PriceListItem ----------------------------------------------------------


class PriceListItemCreate(BaseModel):
    product_id: int
    unit_price: Decimal = Field(ge=0)


class PriceListItemUpdate(BaseModel):
    unit_price: Decimal = Field(ge=0)


class PriceListItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    price_list_id: int
    product_id: int
    unit_price: Decimal
    is_deleted: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime
    created_by: int | None
    updated_by: int | None


# --- ApprovalRequest --------------------------------------------------------


class ApprovalRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    request_type: ApprovalRequestType
    reference_type: str
    reference_id: int
    requested_by: int | None
    reason: str | None
    status: ApprovalStatus
    approved_by: int | None
    decided_at: datetime.datetime | None
    approval_metadata: str | None
    created_at: datetime.datetime


class ApproveRequestPayload(BaseModel):
    reason: str | None = None


class RejectRequestPayload(BaseModel):
    reason: str


# --- SalesInvoice -----------------------------------------------------------


class InvoiceLineCreate(BaseModel):
    product_id: int
    warehouse_id: int
    batch_id: int | None = None
    unit_id: int
    quantity_ordered: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    price_source: PriceSource = PriceSource.PRICE_LIST
    line_discount: Decimal = Field(default=Decimal(0), ge=0)
    line_tax: Decimal = Field(default=Decimal(0), ge=0)


class InvoiceLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_id: int
    product_id: int
    warehouse_id: int
    batch_id: int | None
    unit_id: int
    quantity_ordered: Decimal
    quantity_delivered: Decimal
    unit_price: Decimal
    price_source: PriceSource
    line_discount: Decimal
    line_tax: Decimal
    line_total: Decimal
    stock_movement_id: int | None
    is_deleted: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime
    created_by: int | None
    updated_by: int | None


class SalesInvoiceCreate(BaseModel):
    branch_id: int
    customer_id: int
    salesman_id: int | None = None
    price_list_id: int
    invoice_date: datetime.date
    notes: str | None = None
    lines: list[InvoiceLineCreate] = Field(min_length=1)


class SalesInvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    branch_id: int
    invoice_number: str
    customer_id: int
    salesman_id: int | None
    price_list_id: int
    status: InvoiceStatus
    payment_terms_type: str
    invoice_date: datetime.date
    due_date: datetime.date | None
    posted_at: datetime.datetime | None
    subtotal: Decimal
    total_discount: Decimal
    total_tax: Decimal
    grand_total: Decimal
    amount_collected: Decimal
    notes: str | None
    is_deleted: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime
    created_by: int | None
    updated_by: int | None


class SalesInvoiceDetailResponse(SalesInvoiceResponse):
    lines: list[InvoiceLineResponse] = []


class PostInvoicePayload(BaseModel):
    approved_negative_stock: bool = False


class CancelInvoicePayload(BaseModel):
    reason: str | None = None


# --- CreditNote -------------------------------------------------------------


class CreditNoteLineCreate(BaseModel):
    original_line_id: int
    quantity_returned: Decimal = Field(gt=0)


class CreditNoteLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    credit_note_id: int
    original_line_id: int
    product_id: int
    warehouse_id: int
    batch_id: int | None
    unit_id: int
    quantity_returned: Decimal
    unit_price: Decimal
    line_total: Decimal
    stock_movement_id: int | None
    is_deleted: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime
    created_by: int | None
    updated_by: int | None


class CreditNoteCreate(BaseModel):
    original_invoice_id: int
    credit_note_date: datetime.date
    reason: str | None = None
    lines: list[CreditNoteLineCreate] = Field(min_length=1)


class CreditNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    branch_id: int
    credit_note_number: str
    original_invoice_id: int
    customer_id: int
    status: CreditNoteStatus
    reason: str | None
    credit_note_date: datetime.date
    subtotal: Decimal
    total_tax: Decimal
    total: Decimal
    is_deleted: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime
    created_by: int | None
    updated_by: int | None


class CreditNoteDetailResponse(CreditNoteResponse):
    lines: list[CreditNoteLineResponse] = []


# --- Collection -------------------------------------------------------------


class CollectionLineCreate(BaseModel):
    invoice_id: int
    amount_allocated: Decimal = Field(gt=0)


class CollectionLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    collection_id: int
    invoice_id: int
    amount_allocated: Decimal
    created_at: datetime.datetime
    updated_at: datetime.datetime
    created_by: int | None
    updated_by: int | None


class CollectionCreate(BaseModel):
    branch_id: int
    customer_id: int
    salesman_id: int | None = None
    collection_date: datetime.date
    total_amount: Decimal = Field(gt=0)
    allocation_method: AllocationMethod = AllocationMethod.AUTO
    notes: str | None = None
    lines: list[CollectionLineCreate] = []


class CollectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    branch_id: int
    collection_number: str
    customer_id: int
    salesman_id: int | None
    collection_date: datetime.date
    total_amount: Decimal
    allocation_method: AllocationMethod
    status: CollectionStatus
    notes: str | None
    is_deleted: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime
    created_by: int | None
    updated_by: int | None


class CollectionDetailResponse(CollectionResponse):
    lines: list[CollectionLineResponse] = []
