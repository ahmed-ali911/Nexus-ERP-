"""Scoping columns for *other* modules' tables — not used by Company/Branch/
Warehouse themselves, since those tables define the hierarchy rather than
hang off of it. Every future transactional table mixes these in to get
company_id (+ branch_id) for free.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column


class CompanyScopedMixin:
    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )


class BranchScopedMixin(CompanyScopedMixin):
    branch_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False, index=True
    )
