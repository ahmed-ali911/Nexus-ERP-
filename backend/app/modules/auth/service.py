from __future__ import annotations

import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AuthenticationError, BusinessRuleViolation, NotFoundError
from app.modules.organization.models import Branch, Company

from . import models, schemas, security

# --- Login / tokens --------------------------------------------------------


def authenticate_user(db: Session, company_code: str, username: str, password: str) -> models.User:
    company = db.scalars(
        select(Company).where(Company.code == company_code, Company.is_deleted.is_(False))
    ).first()
    if company is None:
        raise AuthenticationError("Invalid credentials")

    user = db.scalars(
        select(models.User).where(
            models.User.company_id == company.id,
            models.User.username == username,
            models.User.is_deleted.is_(False),
        )
    ).first()
    if user is None:
        raise AuthenticationError("Invalid credentials")

    now = datetime.datetime.now(datetime.UTC)
    if user.locked_until is not None and user.locked_until > now:
        raise AuthenticationError("Account is locked")

    if not user.is_active:
        raise AuthenticationError("Account is inactive")

    if not security.verify_password(password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.MAX_FAILED_LOGIN_ATTEMPTS:
            user.locked_until = now + datetime.timedelta(minutes=settings.LOCKOUT_DURATION_MINUTES)
        db.flush()
        raise AuthenticationError("Invalid credentials")

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    db.flush()
    return user


def login(db: Session, payload: schemas.LoginRequest) -> schemas.TokenResponse:
    user = authenticate_user(db, payload.company_code, payload.username, payload.password)
    access_token = security.create_access_token(user.id, user.company_id)
    refresh_token, expires_at = security.create_refresh_token(user.id)
    db.add(
        models.RefreshToken(
            user_id=user.id, token_hash=security.hash_token(refresh_token), expires_at=expires_at
        )
    )
    db.flush()
    return schemas.TokenResponse(access_token=access_token, refresh_token=refresh_token)


def refresh_access_token(db: Session, refresh_token: str) -> schemas.AccessTokenResponse:
    try:
        payload = security.decode_token(refresh_token)
    except Exception as exc:
        raise AuthenticationError("Invalid refresh token") from exc
    if payload.get("type") != "refresh":
        raise AuthenticationError("Invalid refresh token")

    token_hash = security.hash_token(refresh_token)
    row = db.scalars(
        select(models.RefreshToken).where(models.RefreshToken.token_hash == token_hash)
    ).first()
    now = datetime.datetime.now(datetime.UTC)
    if row is None or row.revoked_at is not None or row.expires_at < now:
        raise AuthenticationError("Invalid refresh token")

    user = db.get(models.User, row.user_id)
    if user is None or user.is_deleted or not user.is_active:
        raise AuthenticationError("Invalid refresh token")

    access_token = security.create_access_token(user.id, user.company_id)
    return schemas.AccessTokenResponse(access_token=access_token)


def logout(db: Session, refresh_token: str) -> None:
    token_hash = security.hash_token(refresh_token)
    row = db.scalars(
        select(models.RefreshToken).where(models.RefreshToken.token_hash == token_hash)
    ).first()
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.datetime.now(datetime.UTC)
        db.flush()


def get_user_permission_codes(db: Session, user: models.User) -> set[str]:
    rows = db.scalars(
        select(models.Permission.code)
        .join(
            models.role_permissions, models.role_permissions.c.permission_id == models.Permission.id
        )
        .join(models.Role, models.Role.id == models.role_permissions.c.role_id)
        .join(models.UserRole, models.UserRole.role_id == models.Role.id)
        .where(models.UserRole.user_id == user.id, models.Role.is_deleted.is_(False))
    )
    return set(rows)


# --- Users -----------------------------------------------------------------


def create_user(
    db: Session, payload: schemas.UserCreate, company_id: int, actor_id: int | None = None
) -> models.User:
    user = models.User(
        company_id=company_id,
        username=payload.username,
        email=payload.email,
        full_name_en=payload.full_name_en,
        full_name_ar=payload.full_name_ar,
        hashed_password=security.hash_password(payload.password),
        is_active=payload.is_active,
        is_superuser=payload.is_superuser,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(user)
    db.flush()
    return user


def get_user(db: Session, user_id: int) -> models.User:
    user = db.get(models.User, user_id)
    if user is None:
        raise NotFoundError(f"User {user_id} not found")
    return user


def list_users(
    db: Session, company_id: int | None = None, include_deleted: bool = False
) -> list[models.User]:
    stmt = select(models.User)
    if company_id is not None:
        stmt = stmt.where(models.User.company_id == company_id)
    if not include_deleted:
        stmt = stmt.where(models.User.is_deleted.is_(False))
    return list(db.scalars(stmt.order_by(models.User.id)))


def update_user(
    db: Session, user_id: int, payload: schemas.UserUpdate, actor_id: int | None = None
) -> models.User:
    user = get_user(db, user_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    user.updated_by = actor_id
    db.flush()
    return user


def soft_delete_user(db: Session, user_id: int, actor_id: int | None = None) -> models.User:
    if actor_id is not None and actor_id == user_id:
        raise BusinessRuleViolation("You cannot delete your own account")
    user = get_user(db, user_id)
    if user.is_deleted:
        return user
    user.is_deleted = True
    user.deleted_at = datetime.datetime.now(datetime.UTC)
    user.updated_by = actor_id
    db.flush()
    return user


def restore_user(db: Session, user_id: int, actor_id: int | None = None) -> models.User:
    user = get_user(db, user_id)
    if not user.is_deleted:
        return user
    user.is_deleted = False
    user.deleted_at = None
    user.updated_by = actor_id
    db.flush()
    return user


# --- Roles -----------------------------------------------------------------


def create_role(
    db: Session,
    payload: schemas.RoleCreate,
    company_id: int,
    actor_id: int | None = None,
    is_system: bool = False,
) -> models.Role:
    role = models.Role(
        company_id=company_id,
        code=payload.code,
        name_en=payload.name_en,
        name_ar=payload.name_ar,
        is_system=is_system,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(role)
    db.flush()
    return role


def get_role(db: Session, role_id: int) -> models.Role:
    role = db.get(models.Role, role_id)
    if role is None:
        raise NotFoundError(f"Role {role_id} not found")
    return role


def list_roles(
    db: Session, company_id: int | None = None, include_deleted: bool = False
) -> list[models.Role]:
    stmt = select(models.Role)
    if company_id is not None:
        stmt = stmt.where(models.Role.company_id == company_id)
    if not include_deleted:
        stmt = stmt.where(models.Role.is_deleted.is_(False))
    return list(db.scalars(stmt.order_by(models.Role.id)))


def update_role(
    db: Session, role_id: int, payload: schemas.RoleUpdate, actor_id: int | None = None
) -> models.Role:
    role = get_role(db, role_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(role, field, value)
    role.updated_by = actor_id
    db.flush()
    return role


def soft_delete_role(db: Session, role_id: int, actor_id: int | None = None) -> models.Role:
    role = get_role(db, role_id)
    if role.is_system:
        raise BusinessRuleViolation("System roles cannot be deleted")
    if role.is_deleted:
        return role
    role.is_deleted = True
    role.deleted_at = datetime.datetime.now(datetime.UTC)
    role.updated_by = actor_id
    db.flush()
    return role


def restore_role(db: Session, role_id: int, actor_id: int | None = None) -> models.Role:
    role = get_role(db, role_id)
    if not role.is_deleted:
        return role
    role.is_deleted = False
    role.deleted_at = None
    role.updated_by = actor_id
    db.flush()
    return role


def set_role_permissions(
    db: Session, role_id: int, permission_codes: list[str], actor_id: int | None = None
) -> models.Role:
    role = get_role(db, role_id)
    permissions = list(
        db.scalars(select(models.Permission).where(models.Permission.code.in_(permission_codes)))
    )
    missing = set(permission_codes) - {p.code for p in permissions}
    if missing:
        raise NotFoundError(f"Unknown permission code(s): {', '.join(sorted(missing))}")
    role.permissions = permissions
    role.updated_by = actor_id
    db.flush()
    return role


# --- Permissions (read-only catalog) ---------------------------------------


def list_permissions(db: Session, module: str | None = None) -> list[models.Permission]:
    stmt = select(models.Permission)
    if module is not None:
        stmt = stmt.where(models.Permission.module == module)
    return list(db.scalars(stmt.order_by(models.Permission.code)))


# --- User <-> Role assignment ------------------------------------------------


def assign_role_to_user(
    db: Session, user_id: int, role_id: int, actor_id: int | None = None
) -> models.UserRole:
    user = get_user(db, user_id)
    role = get_role(db, role_id)
    if role.company_id != user.company_id:
        raise BusinessRuleViolation("Role belongs to a different company")
    existing = db.get(models.UserRole, (user_id, role_id))
    if existing is not None:
        return existing
    user_role = models.UserRole(user_id=user_id, role_id=role_id, assigned_by=actor_id)
    db.add(user_role)
    db.flush()
    return user_role


def unassign_role_from_user(db: Session, user_id: int, role_id: int) -> None:
    existing = db.get(models.UserRole, (user_id, role_id))
    if existing is not None:
        db.delete(existing)
        db.flush()


# --- User <-> Branch assignment (schema-only; no query enforcement yet) -----


def assign_branch_to_user(db: Session, user_id: int, branch_id: int) -> models.UserBranch:
    user = get_user(db, user_id)
    branch = db.get(Branch, branch_id)
    if branch is None:
        raise NotFoundError(f"Branch {branch_id} not found")
    if branch.company_id != user.company_id:
        raise BusinessRuleViolation("Branch belongs to a different company")
    existing = db.get(models.UserBranch, (user_id, branch_id))
    if existing is not None:
        return existing
    user_branch = models.UserBranch(user_id=user_id, branch_id=branch_id)
    db.add(user_branch)
    db.flush()
    return user_branch


def unassign_branch_from_user(db: Session, user_id: int, branch_id: int) -> None:
    existing = db.get(models.UserBranch, (user_id, branch_id))
    if existing is not None:
        db.delete(existing)
        db.flush()
