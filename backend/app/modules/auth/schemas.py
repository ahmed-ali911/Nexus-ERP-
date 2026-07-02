from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# --- Auth flow -------------------------------------------------------------


class LoginRequest(BaseModel):
    company_code: str
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LogoutRequest(BaseModel):
    refresh_token: str


# --- User --------------------------------------------------------------


class UserBase(BaseModel):
    username: str = Field(max_length=50)
    email: EmailStr
    full_name_en: str = Field(max_length=200)
    full_name_ar: str = Field(max_length=200)
    is_active: bool = True


class UserCreate(UserBase):
    # company_id is deliberately NOT here -- the router sets it from the
    # authenticated (superuser) caller's own company_id, never from client input.
    password: str = Field(min_length=8)
    is_superuser: bool = False


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, max_length=50)
    email: EmailStr | None = None
    full_name_en: str | None = Field(default=None, max_length=200)
    full_name_ar: str | None = Field(default=None, max_length=200)
    is_active: bool | None = None
    is_superuser: bool | None = None


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    is_superuser: bool
    last_login_at: datetime | None
    failed_login_attempts: int
    locked_until: datetime | None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    created_by: int | None
    updated_by: int | None


# --- Role ----------------------------------------------------------------


class PermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name_en: str
    name_ar: str
    module: str


class RoleBase(BaseModel):
    code: str = Field(max_length=50)
    name_en: str = Field(max_length=200)
    name_ar: str = Field(max_length=200)


class RoleCreate(RoleBase):
    # company_id and is_system are deliberately NOT here -- company_id comes
    # from the authenticated caller, is_system is developer/seed-only.
    pass


class RoleUpdate(BaseModel):
    code: str | None = Field(default=None, max_length=50)
    name_en: str | None = Field(default=None, max_length=200)
    name_ar: str | None = Field(default=None, max_length=200)


class RoleResponse(RoleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    is_system: bool
    is_deleted: bool
    permissions: list[PermissionResponse] = []
    created_at: datetime
    updated_at: datetime
    created_by: int | None
    updated_by: int | None


class SetRolePermissions(BaseModel):
    permission_codes: list[str]
