from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db

from . import schemas, service
from .dependencies import get_current_user, require_superuser
from .models import User

router = APIRouter(tags=["auth"])

# --- Auth flow ---------------------------------------------------------


@router.post("/auth/login", response_model=schemas.TokenResponse)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    return service.login(db, payload)


@router.post("/auth/refresh", response_model=schemas.AccessTokenResponse)
def refresh(payload: schemas.RefreshRequest, db: Session = Depends(get_db)):
    return service.refresh_access_token(db, payload.refresh_token)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: schemas.LogoutRequest, db: Session = Depends(get_db)):
    service.logout(db, payload.refresh_token)


@router.get("/auth/me", response_model=schemas.UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user


# --- Users (superuser-only) -------------------------------------------------


@router.post("/users", response_model=schemas.UserResponse, status_code=201)
def create_user(
    payload: schemas.UserCreate,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    return service.create_user(
        db, payload, company_id=current_user.company_id, actor_id=current_user.id
    )


@router.get("/users", response_model=list[schemas.UserResponse])
def list_users(
    include_deleted: bool = False,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    return service.list_users(
        db, company_id=current_user.company_id, include_deleted=include_deleted
    )


@router.get("/users/{user_id}", response_model=schemas.UserResponse)
def get_user(
    user_id: int, current_user: User = Depends(require_superuser), db: Session = Depends(get_db)
):
    return service.get_user(db, user_id)


@router.patch("/users/{user_id}", response_model=schemas.UserResponse)
def update_user(
    user_id: int,
    payload: schemas.UserUpdate,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    return service.update_user(db, user_id, payload, actor_id=current_user.id)


@router.delete("/users/{user_id}", response_model=schemas.UserResponse)
def delete_user(
    user_id: int, current_user: User = Depends(require_superuser), db: Session = Depends(get_db)
):
    return service.soft_delete_user(db, user_id, actor_id=current_user.id)


@router.post("/users/{user_id}/restore", response_model=schemas.UserResponse)
def restore_user(
    user_id: int, current_user: User = Depends(require_superuser), db: Session = Depends(get_db)
):
    return service.restore_user(db, user_id, actor_id=current_user.id)


@router.post("/users/{user_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def assign_role(
    user_id: int,
    role_id: int,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    service.assign_role_to_user(db, user_id, role_id, actor_id=current_user.id)


@router.delete("/users/{user_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def unassign_role(
    user_id: int,
    role_id: int,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    service.unassign_role_from_user(db, user_id, role_id)


@router.post("/users/{user_id}/branches/{branch_id}", status_code=status.HTTP_204_NO_CONTENT)
def assign_branch(
    user_id: int,
    branch_id: int,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    service.assign_branch_to_user(db, user_id, branch_id)


@router.delete("/users/{user_id}/branches/{branch_id}", status_code=status.HTTP_204_NO_CONTENT)
def unassign_branch(
    user_id: int,
    branch_id: int,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    service.unassign_branch_from_user(db, user_id, branch_id)


# --- Roles (superuser-only) -------------------------------------------------


@router.post("/roles", response_model=schemas.RoleResponse, status_code=201)
def create_role(
    payload: schemas.RoleCreate,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    return service.create_role(
        db, payload, company_id=current_user.company_id, actor_id=current_user.id
    )


@router.get("/roles", response_model=list[schemas.RoleResponse])
def list_roles(
    include_deleted: bool = False,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    return service.list_roles(
        db, company_id=current_user.company_id, include_deleted=include_deleted
    )


@router.get("/roles/{role_id}", response_model=schemas.RoleResponse)
def get_role(
    role_id: int, current_user: User = Depends(require_superuser), db: Session = Depends(get_db)
):
    return service.get_role(db, role_id)


@router.patch("/roles/{role_id}", response_model=schemas.RoleResponse)
def update_role(
    role_id: int,
    payload: schemas.RoleUpdate,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    return service.update_role(db, role_id, payload, actor_id=current_user.id)


@router.delete("/roles/{role_id}", response_model=schemas.RoleResponse)
def delete_role(
    role_id: int, current_user: User = Depends(require_superuser), db: Session = Depends(get_db)
):
    return service.soft_delete_role(db, role_id, actor_id=current_user.id)


@router.post("/roles/{role_id}/restore", response_model=schemas.RoleResponse)
def restore_role(
    role_id: int, current_user: User = Depends(require_superuser), db: Session = Depends(get_db)
):
    return service.restore_role(db, role_id, actor_id=current_user.id)


@router.put("/roles/{role_id}/permissions", response_model=schemas.RoleResponse)
def set_role_permissions(
    role_id: int,
    payload: schemas.SetRolePermissions,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    return service.set_role_permissions(
        db, role_id, payload.permission_codes, actor_id=current_user.id
    )


# --- Permissions (read-only catalog, superuser-only) ------------------------


@router.get("/permissions", response_model=list[schemas.PermissionResponse])
def list_permissions(
    module: str | None = None,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    return service.list_permissions(db, module=module)
