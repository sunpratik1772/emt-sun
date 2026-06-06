"""Per-request user context for copilot and library helpers."""
from __future__ import annotations

from contextvars import ContextVar

from app.user_scope import SEED_USER_ID

_current_user_id: ContextVar[str | None] = ContextVar("current_user_id", default=None)


def set_current_user_id(user_id: str | None) -> None:
    _current_user_id.set(user_id)


def get_current_user_id() -> str:
    return _current_user_id.get() or SEED_USER_ID
