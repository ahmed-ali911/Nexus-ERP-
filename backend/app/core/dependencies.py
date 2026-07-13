"""Shared FastAPI dependencies for scoping and auditing."""
from __future__ import annotations

from fastapi import Depends

from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User


def get_company_id(current_user: User = Depends(get_current_user)) -> int:
    """Resolve the company_id from the authenticated user's JWT claim."""
    return current_user.company_id


def get_actor_id(current_user: User = Depends(get_current_user)) -> int | None:
    """Resolve the acting user's id for audit trails."""
    return current_user.id
