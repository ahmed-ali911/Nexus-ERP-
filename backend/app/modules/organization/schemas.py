from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import BranchType, WarehouseType

# --- Company -----------------------------------------------------------


class CompanyBase(BaseModel):
    code: str = Field(max_length=20)
    name_en: str = Field(max_length=200)
    name_ar: str = Field(max_length=200)
    commercial_registration_no: str = Field(max_length=50)
    tax_id: str | None = Field(default=None, max_length=50)
    base_currency: str = Field(default="KWD", max_length=3)
    timezone: str = Field(default="Asia/Kuwait", max_length=50)
    is_active: bool = True


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    code: str | None = Field(default=None, max_length=20)
    name_en: str | None = Field(default=None, max_length=200)
    name_ar: str | None = Field(default=None, max_length=200)
    commercial_registration_no: str | None = Field(default=None, max_length=50)
    tax_id: str | None = Field(default=None, max_length=50)
    base_currency: str | None = Field(default=None, max_length=3)
    timezone: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None


class CompanyResponse(CompanyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_deleted: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    created_by: int | None
    updated_by: int | None


# --- Branch --------------------------------------------------------------


class BranchBase(BaseModel):
    code: str = Field(max_length=20)
    name_en: str = Field(max_length=200)
    name_ar: str = Field(max_length=200)
    branch_type: BranchType
    address: str | None = None
    phone: str | None = Field(default=None, max_length=30)
    is_active: bool = True


class BranchCreate(BranchBase):
    company_id: int


class BranchUpdate(BaseModel):
    code: str | None = Field(default=None, max_length=20)
    name_en: str | None = Field(default=None, max_length=200)
    name_ar: str | None = Field(default=None, max_length=200)
    branch_type: BranchType | None = None
    address: str | None = None
    phone: str | None = Field(default=None, max_length=30)
    is_active: bool | None = None


class BranchResponse(BranchBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    is_deleted: bool
    deleted_at: datetime | None
    deleted_by_cascade: bool
    created_at: datetime
    updated_at: datetime
    created_by: int | None
    updated_by: int | None


# --- Warehouse -------------------------------------------------------------


class WarehouseBase(BaseModel):
    code: str = Field(max_length=20)
    name_en: str = Field(max_length=200)
    name_ar: str = Field(max_length=200)
    warehouse_type: WarehouseType
    is_active: bool = True


class WarehouseCreate(WarehouseBase):
    branch_id: int


class WarehouseUpdate(BaseModel):
    code: str | None = Field(default=None, max_length=20)
    name_en: str | None = Field(default=None, max_length=200)
    name_ar: str | None = Field(default=None, max_length=200)
    warehouse_type: WarehouseType | None = None
    is_active: bool | None = None


class WarehouseResponse(WarehouseBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    branch_id: int
    is_deleted: bool
    deleted_at: datetime | None
    deleted_by_cascade: bool
    created_at: datetime
    updated_at: datetime
    created_by: int | None
    updated_by: int | None
