from __future__ import annotations

import datetime
import enum

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.mixins import AuditMixin, TimestampMixin
from app.modules.organization.mixins import CompanyScopedMixin


class ApprovalRequestType(enum.StrEnum):
    # Sales approvals
    CREDIT_LIMIT_OVERRIDE = "CREDIT_LIMIT_OVERRIDE"
    NEGATIVE_STOCK = "NEGATIVE_STOCK"
    DISCOUNT_OVERRIDE = "DISCOUNT_OVERRIDE"
    MANUAL_PRICE = "MANUAL_PRICE"
    CANCEL_AFTER_POST = "CANCEL_AFTER_POST"
    BACKDATED_INVOICE = "BACKDATED_INVOICE"
    # Purchasing approvals
    PURCHASE_PRICE_OVERRIDE = "PURCHASE_PRICE_OVERRIDE"
    CANCEL_GRN = "CANCEL_GRN"
    CANCEL_SUPPLIER_INVOICE = "CANCEL_SUPPLIER_INVOICE"
    PURCHASE_RETURN = "PURCHASE_RETURN"
    BACKDATED_PURCHASE_DOC = "BACKDATED_PURCHASE_DOC"
    SUPPLIER_CREDIT_LIMIT_OVERRIDE = "SUPPLIER_CREDIT_LIMIT_OVERRIDE"


class ApprovalStatus(enum.StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ApprovalRequest(Base, CompanyScopedMixin, TimestampMixin, AuditMixin):
    __tablename__ = "approval_requests"
    __table_args__ = (
        Index(
            "ix_approval_requests_ref",
            "reference_type",
            "reference_id",
            "request_type",
            "status",
        ),
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
    decided_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approval_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)
