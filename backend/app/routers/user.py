"""Per-user preferences, data-source access, and admin user management."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth_deps import require_admin_user, require_user_id
from app.database_scope import (
    create_provisioned_user,
    delete_user_account,
    get_admin_overview,
    get_good_example_promotion_prefs,
    list_data_source_access_rows,
    list_feature_access_rows,
    list_public_users,
    list_skill_access_rows,
    set_data_source_access,
    set_feature_access,
    set_good_example_promotion_prefs,
    set_skill_access,
    set_user_role,
)
from app.user_scope import ROLE_ADMIN, ROLE_USER, user_is_admin

router = APIRouter(prefix="/user", tags=["user"])


class DataSourceAccessUpdate(BaseModel):
    has_access: bool


class SkillAccessUpdate(BaseModel):
    has_access: bool


class FeatureAccessUpdate(BaseModel):
    enabled: bool


class GoodExamplePrefsUpdate(BaseModel):
    promote_to_folder: bool | None = None
    promote_to_table: bool | None = None


class CreateUserBody(BaseModel):
    first_name: str = Field(min_length=1, max_length=64)
    last_name: str = Field(min_length=1, max_length=64)
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8)
    data_source_access: dict[str, bool] = Field(default_factory=dict)
    skill_access: dict[str, bool] = Field(default_factory=dict)
    feature_access: dict[str, bool] = Field(default_factory=dict)
    role: str = Field(default=ROLE_USER)


class UpdateUserRoleBody(BaseModel):
    role: str


@router.get("/data-source-access")
def get_data_source_access(user_id: str = Depends(require_user_id)) -> dict:
    return {"sources": list_data_source_access_rows(user_id)}


@router.put("/data-source-access/{source_id}")
def update_data_source_access(
    source_id: str,
    body: DataSourceAccessUpdate,
    user_id: str = Depends(require_user_id),
) -> dict:
    source_id = (source_id or "").strip()
    if not source_id:
        raise HTTPException(status_code=400, detail="source_id is required")
    set_data_source_access(user_id, source_id, body.has_access)
    return {"source_id": source_id, "has_access": body.has_access}


@router.get("/preferences/good-examples")
def get_good_example_preferences(user_id: str = Depends(require_user_id)) -> dict:
    return get_good_example_promotion_prefs(user_id)


@router.put("/preferences/good-examples")
def update_good_example_preferences(
    body: GoodExamplePrefsUpdate,
    user_id: str = Depends(require_user_id),
) -> dict:
    return set_good_example_promotion_prefs(
        user_id,
        promote_to_folder=body.promote_to_folder,
        promote_to_table=body.promote_to_table,
    )


@router.get("/users")
def list_users(_admin: dict = Depends(require_admin_user)) -> dict:
    return {"users": list_public_users()}


@router.get("/admin/overview")
def admin_overview(_admin: dict = Depends(require_admin_user)) -> dict:
    return get_admin_overview()


@router.post("/users")
def create_user(body: CreateUserBody, _admin: dict = Depends(require_admin_user)) -> dict:
    try:
        user = create_provisioned_user(
            first_name=body.first_name,
            last_name=body.last_name,
            username=body.username,
            password=body.password,
            data_source_access=body.data_source_access,
            skill_access=body.skill_access or None,
            feature_access=body.feature_access or None,
            role=body.role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"user": user}


@router.put("/users/{user_id}/role")
def update_user_role(
    user_id: str,
    body: UpdateUserRoleBody,
    admin: dict = Depends(require_admin_user),
) -> dict:
    target_id = (user_id or "").strip()
    if not target_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    normalized = (body.role or ROLE_USER).strip().lower()
    if normalized not in {ROLE_ADMIN, ROLE_USER}:
        raise HTTPException(status_code=400, detail="role must be 'admin' or 'user'")

    if str(admin.get("user_id") or "") == target_id and normalized != ROLE_ADMIN:
        admin_count = sum(1 for u in list_public_users() if u.get("role") == ROLE_ADMIN)
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot remove the last admin")

    try:
        user = set_user_role(target_id, normalized)
    except ValueError as exc:
        msg = str(exc)
        status = 404 if "not found" in msg else 400
        raise HTTPException(status_code=status, detail=msg) from exc
    return {"user": user}


@router.delete("/users/{user_id}")
def remove_user(user_id: str, admin: dict = Depends(require_admin_user)) -> dict:
    target_id = (user_id or "").strip()
    if not target_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    if str(admin.get("user_id") or "") == target_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    target = next((u for u in list_public_users() if u.get("user_id") == target_id), None)
    if target and user_is_admin(target):
        admin_count = sum(1 for u in list_public_users() if u.get("role") == ROLE_ADMIN)
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot delete the last admin")

    try:
        return delete_user_account(target_id)
    except ValueError as exc:
        msg = str(exc)
        status = 404 if "not found" in msg else 400
        raise HTTPException(status_code=status, detail=msg) from exc


@router.get("/users/{user_id}/data-source-access")
def admin_get_user_data_source_access(
    user_id: str,
    _admin: dict = Depends(require_admin_user),
) -> dict:
    target_id = (user_id or "").strip()
    return {"sources": list_data_source_access_rows(target_id)}


@router.put("/users/{user_id}/data-source-access/{source_id}")
def admin_update_user_data_source_access(
    user_id: str,
    source_id: str,
    body: DataSourceAccessUpdate,
    _admin: dict = Depends(require_admin_user),
) -> dict:
    target_id = (user_id or "").strip()
    source_id = (source_id or "").strip()
    if not target_id or not source_id:
        raise HTTPException(status_code=400, detail="user_id and source_id are required")
    set_data_source_access(target_id, source_id, body.has_access)
    return {"source_id": source_id, "has_access": body.has_access}


@router.get("/users/{user_id}/skill-access")
def admin_get_user_skill_access(
    user_id: str,
    _admin: dict = Depends(require_admin_user),
) -> dict:
    target_id = (user_id or "").strip()
    return {"skills": list_skill_access_rows(target_id)}


@router.put("/users/{user_id}/skill-access/{skill_id}")
def admin_update_user_skill_access(
    user_id: str,
    skill_id: str,
    body: SkillAccessUpdate,
    _admin: dict = Depends(require_admin_user),
) -> dict:
    target_id = (user_id or "").strip()
    skill_id = (skill_id or "").strip()
    if not target_id or not skill_id:
        raise HTTPException(status_code=400, detail="user_id and skill_id are required")
    set_skill_access(target_id, skill_id, body.has_access)
    return {"skill_id": skill_id, "has_access": body.has_access}


@router.get("/users/{user_id}/feature-access")
def admin_get_user_feature_access(
    user_id: str,
    _admin: dict = Depends(require_admin_user),
) -> dict:
    target_id = (user_id or "").strip()
    return {"features": list_feature_access_rows(target_id)}


@router.put("/users/{user_id}/feature-access/{feature_key}")
def admin_update_user_feature_access(
    user_id: str,
    feature_key: str,
    body: FeatureAccessUpdate,
    _admin: dict = Depends(require_admin_user),
) -> dict:
    target_id = (user_id or "").strip()
    feature_key = (feature_key or "").strip()
    if not target_id or not feature_key:
        raise HTTPException(status_code=400, detail="user_id and feature_key are required")
    try:
        set_feature_access(target_id, feature_key, body.enabled)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"feature_key": feature_key, "enabled": body.enabled}
