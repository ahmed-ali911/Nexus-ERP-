"""Reusable columns for every module table: timestamps, audit, soft-delete."""

from __future__ import annotations

import datetime

from sqlalchemy import Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AuditMixin:
    # Not FK-constrained yet: the users table doesn't exist until RBAC/Users lands.
    # Add the FK constraint in a follow-up migration once it does.
    created_by: Mapped[int | None] = mapped_column(nullable=True)
    updated_by: Mapped[int | None] = mapped_column(nullable=True)


class SoftDeleteMixin:
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
