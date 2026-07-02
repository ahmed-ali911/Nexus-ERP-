from __future__ import annotations

import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from .models import CostingMethod, MovementType

# --- InventorySettings ---------------------------------------------------


class InventorySettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    costing_method: CostingMethod
    allow_negative_stock: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime
    created_by: int | None
    updated_by: int | None


class InventorySettingsUpdate(BaseModel):
    allow_negative_stock: bool | None = None


# --- Batch ---------------------------------------------------------------


class BatchCreate(BaseModel):
    product_id: int
    batch_number: str = Field(max_length=100)
    expiry_date: datetime.date | None = None
    notes: str | None = None


class BatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    product_id: int
    batch_number: str
    expiry_date: datetime.date | None
    notes: str | None
    is_deleted: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime
    created_by: int | None
    updated_by: int | None


# --- Stock Movement requests ---------------------------------------------


class ReceiveStockRequest(BaseModel):
    warehouse_id: int
    product_id: int
    batch_id: int | None = None
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(ge=0)
    notes: str | None = None


class IssueStockRequest(BaseModel):
    warehouse_id: int
    product_id: int
    batch_id: int | None = None
    quantity: Decimal = Field(gt=0)
    notes: str | None = None
    approved_negative: bool = False


class TransferStockRequest(BaseModel):
    from_warehouse_id: int
    to_warehouse_id: int
    product_id: int
    batch_id: int | None = None
    quantity: Decimal = Field(gt=0)
    notes: str | None = None
    approved_negative: bool = False


class AdjustStockRequest(BaseModel):
    warehouse_id: int
    product_id: int
    batch_id: int | None = None
    # Positive = stock increase, negative = stock decrease
    quantity_delta: Decimal
    unit_cost: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None
    approved_negative: bool = False


# --- Stock Movement response ---------------------------------------------


class StockMovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    warehouse_id: int
    product_id: int
    batch_id: int | None
    movement_type: MovementType
    quantity: Decimal
    unit_cost: Decimal
    total_cost: Decimal
    reference_id: int | None
    reference_type: str | None
    notes: str | None
    approved_negative: bool
    created_at: datetime.datetime
    created_by: int | None


# --- Stock Balance response ----------------------------------------------


class StockBalanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    warehouse_id: int
    product_id: int
    batch_id: int | None
    quantity_on_hand: Decimal
    weighted_avg_cost: Decimal
    updated_at: datetime.datetime
