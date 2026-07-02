from __future__ import annotations

import enum

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, String, Text, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.mixins import AuditMixin, SoftDeleteMixin, TimestampMixin


class BranchType(enum.StrEnum):
    FACTORY = "FACTORY"
    RETAIL = "RETAIL"
    BOTH = "BOTH"


class WarehouseType(enum.StrEnum):
    RAW_MATERIAL = "RAW_MATERIAL"
    FINISHED_GOODS = "FINISHED_GOODS"
    GENERAL = "GENERAL"


class Company(Base, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "companies"
    __table_args__ = (
        Index(
            "uq_companies_code", "code", unique=True, postgresql_where=text("is_deleted = false")
        ),
        Index(
            "uq_companies_cr_no",
            "commercial_registration_no",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name_en: Mapped[str] = mapped_column(String(200), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    commercial_registration_no: Mapped[str] = mapped_column(String(50), nullable=False)
    tax_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    base_currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="KWD", server_default="KWD"
    )
    timezone: Mapped[str] = mapped_column(
        String(50), nullable=False, default="Asia/Kuwait", server_default="Asia/Kuwait"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    branches: Mapped[list[Branch]] = relationship(back_populates="company")


class Branch(Base, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "branches"
    __table_args__ = (
        Index(
            "uq_branches_company_code",
            "company_id",
            "code",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name_en: Mapped[str] = mapped_column(String(200), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    branch_type: Mapped[BranchType] = mapped_column(
        SAEnum(
            BranchType,
            native_enum=False,
            validate_strings=True,
            length=20,
            name="ck_branches_branch_type",
        ),
        nullable=False,
    )
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    # True if this branch was soft-deleted as a side effect of its company being
    # soft-deleted, rather than deleted directly. Lets restore_company() only
    # bring back children it cascaded onto, not ones deleted independently.
    deleted_by_cascade: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    company: Mapped[Company] = relationship(back_populates="branches")
    warehouses: Mapped[list[Warehouse]] = relationship(back_populates="branch")


class Warehouse(Base, TimestampMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "warehouses"
    __table_args__ = (
        Index(
            "uq_warehouses_branch_code",
            "branch_id",
            "code",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    branch_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name_en: Mapped[str] = mapped_column(String(200), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    warehouse_type: Mapped[WarehouseType] = mapped_column(
        SAEnum(
            WarehouseType,
            native_enum=False,
            validate_strings=True,
            length=20,
            name="ck_warehouses_warehouse_type",
        ),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    deleted_by_cascade: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    branch: Mapped[Branch] = relationship(back_populates="warehouses")
