import datetime

import jwt
import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.exceptions import AuthenticationError, BusinessRuleViolation
from app.modules.auth import schemas, security, service
from app.modules.auth.dependencies import require_permission
from app.modules.auth.models import Permission
from app.modules.organization import schemas as org_schemas
from app.modules.organization import service as org_service
from app.modules.organization.models import BranchType


def _make_company(db, code="ACME"):
    return org_service.create_company(
        db,
        org_schemas.CompanyCreate(
            code=code,
            name_en=f"{code} Co",
            name_ar=f"شركة {code}",
            commercial_registration_no=f"CR-{code}",
        ),
    )


def _make_user(db, company_id, username="jdoe", password="Password123!", is_superuser=False):
    return service.create_user(
        db,
        schemas.UserCreate(
            username=username,
            email=f"{username}@example.com",
            full_name_en="Test User",
            full_name_ar="مستخدم تجريبي",
            password=password,
            is_superuser=is_superuser,
        ),
        company_id=company_id,
    )


def _make_role(db, company_id, code="ROLE1", permission_codes=None):
    role = service.create_role(
        db, schemas.RoleCreate(code=code, name_en=code, name_ar=code), company_id=company_id
    )
    if permission_codes:
        service.set_role_permissions(db, role.id, permission_codes)
    return role


def _make_permission(db, code, module=None):
    permission = Permission(
        code=code, name_en=code, name_ar=code, module=module or code.split(".")[0]
    )
    db.add(permission)
    db.flush()
    return permission


# --- login ---------------------------------------------------------------


def test_login_success(db_session):
    company = _make_company(db_session, code="LOGINCO")
    _make_user(db_session, company.id, username="jdoe", password="Password123!")

    tokens = service.login(
        db_session,
        schemas.LoginRequest(company_code="LOGINCO", username="jdoe", password="Password123!"),
    )
    assert tokens.access_token
    assert tokens.refresh_token
    assert tokens.token_type == "bearer"


def test_login_wrong_password_increments_failed_attempts(db_session):
    company = _make_company(db_session, code="WRONGPW")
    user = _make_user(db_session, company.id, username="jdoe", password="Password123!")

    with pytest.raises(AuthenticationError):
        service.authenticate_user(db_session, "WRONGPW", "jdoe", "bad-password")

    db_session.refresh(user)
    assert user.failed_login_attempts == 1
    assert user.locked_until is None


def test_login_locked_after_max_failed_attempts(db_session):
    company = _make_company(db_session, code="LOCKCO")
    user = _make_user(db_session, company.id, username="jdoe", password="Password123!")

    for _ in range(settings.MAX_FAILED_LOGIN_ATTEMPTS):
        with pytest.raises(AuthenticationError):
            service.authenticate_user(db_session, "LOCKCO", "jdoe", "bad-password")

    db_session.refresh(user)
    assert user.locked_until is not None
    assert user.locked_until > datetime.datetime.now(datetime.UTC)

    # even the CORRECT password is rejected while locked
    with pytest.raises(AuthenticationError):
        service.authenticate_user(db_session, "LOCKCO", "jdoe", "Password123!")


def test_login_resets_failed_attempts_on_success(db_session):
    company = _make_company(db_session, code="RESETCO")
    user = _make_user(db_session, company.id, username="jdoe", password="Password123!")

    for _ in range(3):
        with pytest.raises(AuthenticationError):
            service.authenticate_user(db_session, "RESETCO", "jdoe", "bad-password")
    db_session.refresh(user)
    assert user.failed_login_attempts == 3

    service.authenticate_user(db_session, "RESETCO", "jdoe", "Password123!")
    db_session.refresh(user)
    assert user.failed_login_attempts == 0
    assert user.locked_until is None
    assert user.last_login_at is not None


# --- JWT -------------------------------------------------------------------


def test_access_token_round_trips_claims(db_session):
    company = _make_company(db_session, code="JWTCO")
    user = _make_user(db_session, company.id, username="jdoe")

    token = security.create_access_token(user.id, user.company_id)
    payload = security.decode_token(token)

    assert payload["sub"] == str(user.id)
    assert payload["company_id"] == user.company_id
    assert payload["type"] == "access"


def test_expired_token_rejected():
    now = datetime.datetime.now(datetime.UTC)
    expired_payload = {
        "sub": "1",
        "company_id": 1,
        "type": "access",
        "iat": now - datetime.timedelta(hours=1),
        "exp": now - datetime.timedelta(minutes=1),
    }
    token = jwt.encode(expired_payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    with pytest.raises(jwt.ExpiredSignatureError):
        security.decode_token(token)


def test_invalid_signature_token_rejected():
    now = datetime.datetime.now(datetime.UTC)
    payload = {
        "sub": "1",
        "company_id": 1,
        "type": "access",
        "iat": now,
        "exp": now + datetime.timedelta(minutes=30),
    }
    token = jwt.encode(
        payload, "a-completely-different-secret-key-value", algorithm=settings.JWT_ALGORITHM
    )

    with pytest.raises(jwt.InvalidSignatureError):
        security.decode_token(token)


# --- require_permission -----------------------------------------------------


def test_require_permission_allows_with_permission(db_session):
    company = _make_company(db_session, code="PERMCO")
    _make_permission(db_session, "test.widget.create")
    role = _make_role(
        db_session, company.id, code="CREATOR", permission_codes=["test.widget.create"]
    )
    user = _make_user(db_session, company.id, username="creator")
    service.assign_role_to_user(db_session, user.id, role.id)

    dependency = require_permission("test.widget.create")
    result = dependency(current_user=user, db=db_session)
    assert result is user


def test_require_permission_403_without_permission(db_session):
    company = _make_company(db_session, code="NOPERMCO")
    _make_permission(db_session, "test.widget.create")
    user = _make_user(db_session, company.id, username="nobody")

    dependency = require_permission("test.widget.create")
    with pytest.raises(HTTPException) as exc_info:
        dependency(current_user=user, db=db_session)
    assert exc_info.value.status_code == 403


def test_require_permission_superuser_bypasses_check(db_session):
    company = _make_company(db_session, code="SUPERCO")
    user = _make_user(db_session, company.id, username="root", is_superuser=True)

    dependency = require_permission("test.widget.create")
    result = dependency(current_user=user, db=db_session)
    assert result is user


# --- business rules ----------------------------------------------------


def test_cannot_assign_role_from_different_company(db_session):
    company_a = _make_company(db_session, code="COA")
    company_b = _make_company(db_session, code="COB")
    user = _make_user(db_session, company_a.id, username="jdoe")
    role_b = _make_role(db_session, company_b.id, code="ROLEB")

    with pytest.raises(BusinessRuleViolation):
        service.assign_role_to_user(db_session, user.id, role_b.id)


def test_cannot_delete_system_role(db_session):
    company = _make_company(db_session, code="SYSCO")
    role = service.create_role(
        db_session,
        schemas.RoleCreate(code="SYS_ADMIN", name_en="Admin", name_ar="مدير"),
        company_id=company.id,
        is_system=True,
    )
    with pytest.raises(BusinessRuleViolation):
        service.soft_delete_role(db_session, role.id)


def test_cannot_delete_own_account(db_session):
    company = _make_company(db_session, code="SELFCO")
    user = _make_user(db_session, company.id, username="jdoe")

    with pytest.raises(BusinessRuleViolation):
        service.soft_delete_user(db_session, user.id, actor_id=user.id)


# --- audit threading ---------------------------------------------------


def test_created_by_populated_for_authenticated_user(db_session):
    company = _make_company(db_session, code="AUDITCO")
    user = _make_user(db_session, company.id, username="jdoe")

    branch = org_service.create_branch(
        db_session,
        org_schemas.BranchCreate(
            company_id=company.id,
            code="B1",
            name_en="Branch 1",
            name_ar="فرع 1",
            branch_type=BranchType.RETAIL,
        ),
        actor_id=user.id,
    )
    assert branch.created_by == user.id
    assert branch.updated_by == user.id


def test_username_unique_within_company(db_session):
    company = _make_company(db_session, code="DUPUSER")
    _make_user(db_session, company.id, username="jdoe")
    with pytest.raises(IntegrityError):
        _make_user(db_session, company.id, username="jdoe", password="Different123!")
