from __future__ import annotations

from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db

from . import security, service
from .models import User

# HTTPBearer (not OAuth2PasswordBearer): our login endpoint takes a JSON body
# (company_code/username/password), not the OAuth2 password-grant form, so
# OAuth2PasswordBearer's tokenUrl semantics don't apply -- we only need
# "extract the Authorization: Bearer <token> header" from this.
bearer_scheme = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise _UNAUTHORIZED
    try:
        payload = security.decode_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise _UNAUTHORIZED from exc
    if payload.get("type") != "access":
        raise _UNAUTHORIZED
    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError, TypeError) as exc:
        raise _UNAUTHORIZED from exc

    user = db.get(User, user_id)
    if user is None or user.is_deleted or not user.is_active:
        raise _UNAUTHORIZED
    return user


def require_superuser(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Superuser privileges required"
        )
    return current_user


def require_permission(code: str) -> Callable[..., User]:
    def dependency(
        current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
    ) -> User:
        if current_user.is_superuser:
            return current_user
        if code not in service.get_user_permission_codes(db, current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=f"Missing permission: {code}"
            )
        return current_user

    return dependency
