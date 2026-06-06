"""
Email/password + Emergent-managed Google Auth.

Endpoints:
  POST /api/auth/register   Create a user with email+password, drop a
                            session cookie, return the user.
  POST /api/auth/login      Email+password sign-in, drop a session
                            cookie, return the user.
  POST /api/auth/session    Exchange a one-time `session_id` (from the
                            Google OAuth callback URL fragment) for a
                            7-day `session_token`.
  GET  /api/auth/me         Return the current user (or 401). Reads
                            `session_token` from cookie first, falls
                            back to `Authorization: Bearer …`.
  POST /api/auth/logout     Delete the session row + clear the cookie.

Storage:
  Mongo collections `users` (one row per email) and `user_sessions`
  (one row per active token). Email-registered users get a
  `password_hash` field; Google-OAuth users don't. All queries pass
  `{"_id": 0}` so we never leak Mongo's ObjectId.
"""
from __future__ import annotations

import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import httpx
from fastapi import APIRouter, Cookie, Header, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field

from .. import database as db

router = APIRouter(prefix="/auth", tags=["auth"])

_EMERGENT_AUTH_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"
_SESSION_TTL = timedelta(days=7)
_COOKIE_NAME = "session_token"
_MIN_PW_LEN = 8


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------
def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Cookie / session helpers
# ---------------------------------------------------------------------------
def _set_session_cookie(response: Response, token: str) -> None:
    """Apply the same cookie config to every auth path."""
    secure = os.environ.get("DBSHERPA_COOKIE_SECURE", "").strip().lower() in ("1", "true", "yes")
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=secure,
        samesite="none" if secure else "lax",
        path="/",
        max_age=int(_SESSION_TTL.total_seconds()),
    )


async def _create_session(user_id: str) -> tuple[str, datetime]:
    """Mint a fresh opaque session token and persist it."""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + _SESSION_TTL
    db.create_session(user_id, token, expires_at)
    return token, expires_at


async def _resolve_session_token(
    cookie_token: str | None,
    auth_header: str | None,
) -> str | None:
    """Cookie wins, fall back to `Authorization: Bearer …`."""
    if cookie_token:
        return cookie_token
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip() or None
    return None


def _public_user(user: dict) -> dict:
    """User dict safe to send to the client. Strips password_hash."""
    from ..user_scope import ROLE_USER

    return {
        "user_id": user["user_id"],
        "username": user.get("username"),
        "email": user["email"],
        "name": user.get("name") or user["email"],
        "picture": user.get("picture"),
        "role": str(user.get("role") or ROLE_USER).strip().lower(),
    }


async def get_current_user(
    session_token: str | None = Cookie(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    """FastAPI dependency that returns the authenticated user dict, or 401."""
    token = await _resolve_session_token(session_token, authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    sess = db.get_session(token)
    if not sess:
        raise HTTPException(status_code=401, detail="Invalid session")

    expires_at = sess.get("expires_at")
    if isinstance(expires_at, str):
        try:
            expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        except Exception:
            expires_at = datetime.strptime(expires_at.split(".")[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at and expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")

    user = db.get_user_by_id(sess["user_id"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


# ---------------------------------------------------------------------------
# Email / password endpoints
# ---------------------------------------------------------------------------
class RegisterBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=_MIN_PW_LEN)
    name: str | None = None
    username: str | None = Field(default=None, min_length=3, max_length=64)


class LoginBody(BaseModel):
    email: EmailStr | None = None
    username: str | None = None
    password: str


@router.post("/register")
async def register(body: RegisterBody, response: Response) -> dict:
    """Create a brand-new email-backed user."""
    email = body.email.lower().strip()

    if db.get_user_by_email(email):
        raise HTTPException(status_code=409, detail="Email already registered")

    user_id = f"user_{uuid.uuid4().hex[:12]}"
    name = (body.name or email.split("@")[0]).strip()
    db.save_user(
        user_id=user_id,
        email=email,
        name=name,
        picture=None,
        password_hash=_hash_password(body.password),
        auth_provider="email",
        username=body.username,
    )
    token, expires_at = await _create_session(user_id)
    _set_session_cookie(response, token)
    return {
        "user": {
            "user_id": user_id,
            "username": body.username or email.split("@")[0],
            "email": email,
            "name": name,
            "picture": None,
        },
        "session_token": token,
        "expires_at": expires_at.isoformat(),
    }


@router.post("/login")
async def login(body: LoginBody, response: Response) -> dict:
    """Username or email + password sign-in."""
    from ..database_scope import get_user_by_username

    if not body.username and not body.email:
        raise HTTPException(status_code=400, detail="username or email is required")

    user = None
    if body.username:
        user = get_user_by_username(body.username.strip().lower())
    elif body.email:
        user = db.get_user_by_email(body.email.lower().strip())
    if not user or not user.get("password_hash"):
        raise HTTPException(status_code=401, detail="Invalid username/email or password")
    if not _verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username/email or password")

    db.update_user_login(user["user_id"])
    token, expires_at = await _create_session(user["user_id"])
    _set_session_cookie(response, token)
    return {
        "user": _public_user(user),
        "session_token": token,
        "expires_at": expires_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Google OAuth (Emergent-managed)
# ---------------------------------------------------------------------------
class SessionCreateBody(BaseModel):
    session_id: str


@router.post("/session")
async def create_session(body: SessionCreateBody, response: Response) -> dict:
    """Exchange the OAuth-callback `session_id` for a persistent session."""
    if not body.session_id:
        raise HTTPException(status_code=400, detail="session_id required")

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            r = await client.get(
                _EMERGENT_AUTH_URL,
                headers={"X-Session-ID": body.session_id},
            )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Auth upstream error: {exc}")
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail=f"OAuth rejected: {r.text[:200]}")
    payload: dict[str, Any] = r.json()

    email = (payload.get("email") or "").lower().strip()
    name = payload.get("name") or email or "User"
    picture = payload.get("picture")
    upstream_token = payload.get("session_token")
    if not email or not upstream_token:
        raise HTTPException(status_code=502, detail="Auth upstream payload incomplete")

    existing = db.get_user_by_email(email)
    if existing:
        user_id = existing["user_id"]
        db.update_user_login(user_id, name=name, picture=picture)
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        db.save_user(
            user_id=user_id,
            email=email,
            name=name,
            picture=picture,
            password_hash=None,
            auth_provider="google",
        )

    expires_at = datetime.now(timezone.utc) + _SESSION_TTL
    db.create_session(user_id, upstream_token, expires_at)
    _set_session_cookie(response, upstream_token)

    return {
        "user": {
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
        },
        "session_token": upstream_token,
        "expires_at": expires_at.isoformat(),
    }


@router.get("/me")
async def me(
    session_token: str | None = Cookie(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    user = await get_current_user(session_token, authorization)
    return _public_user(user)


@router.post("/logout")
async def logout(
    response: Response,
    session_token: str | None = Cookie(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    token = await _resolve_session_token(session_token, authorization)
    if token:
        db.delete_session(token)
    response.delete_cookie(_COOKIE_NAME, path="/", samesite="none", secure=True)
    return {"ok": True}
