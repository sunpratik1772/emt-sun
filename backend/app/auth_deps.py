"""Shared FastAPI auth dependencies for user-scoped endpoints."""
from __future__ import annotations

from fastapi import Cookie, Depends, Header, HTTPException

from app.user_scope import USER_FEATURES, user_is_admin

from .routers.auth import _resolve_session_token, get_current_user


async def require_user(
    session_token: str | None = Cookie(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    """Return the authenticated user or 401."""
    return await get_current_user(session_token, authorization)


async def require_user_id(
    session_token: str | None = Cookie(default=None),
    authorization: str | None = Header(default=None),
) -> str:
    """Return authenticated user_id or 401."""
    user = await require_user(session_token, authorization)
    user_id = str(user.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user session")
    return user_id


def feature_guard(feature: str):
    """FastAPI dependency factory — block when a feature is disabled for the user."""

    async def _guard(user_id: str = Depends(require_user_id)) -> str:
        from app.database_scope import user_has_feature

        if not user_has_feature(user_id, feature):
            label = USER_FEATURES.get(feature, feature)
            raise HTTPException(status_code=403, detail=f"{label} is disabled for this account")
        return user_id

    return _guard


async def resolve_user_id(
    session_token: str | None = Cookie(default=None),
    authorization: str | None = Header(default=None),
) -> str | None:
    """Return user_id when a valid session exists, else None."""
    token = await _resolve_session_token(session_token, authorization)
    if not token:
        return None
    from . import database as db

    sess = db.get_session(token)
    if not sess:
        return None
    return str(sess.get("user_id") or "").strip() or None


async def require_admin_user(
    session_token: str | None = Cookie(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    """Only users with role=admin may access admin endpoints."""
    user = await require_user(session_token, authorization)
    if not user_is_admin(user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
