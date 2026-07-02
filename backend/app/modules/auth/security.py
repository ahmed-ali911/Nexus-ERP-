from __future__ import annotations

import datetime
import hashlib

import bcrypt
import jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def hash_token(token: str) -> str:
    """Fast deterministic hash for refresh-token lookup/revocation.

    Not bcrypt: bcrypt's per-call random salt makes it unsuitable for
    lookup-by-exact-match, and its slowness defends against brute-forcing a
    *low-entropy* secret like a password -- a JWT already carries 100+ bits
    of signature entropy, so SHA-256 is the right tool here.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(user_id: int, company_id: int) -> str:
    now = datetime.datetime.now(datetime.UTC)
    payload = {
        "sub": str(user_id),
        "company_id": company_id,
        "type": "access",
        "iat": now,
        "exp": now + datetime.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: int) -> tuple[str, datetime.datetime]:
    now = datetime.datetime.now(datetime.UTC)
    expires_at = now + datetime.timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, expires_at


def decode_token(token: str) -> dict:
    """Raises jwt.PyJWTError (or a subclass) on any invalid/expired token."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
