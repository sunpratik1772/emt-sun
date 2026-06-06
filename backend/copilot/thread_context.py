"""Copilot thread memory — sync in-memory history and format for LLM context."""
from __future__ import annotations

import re
from typing import Any

_THREAD_ARTIFACT = re.compile(
    r"\b(built|created|workflow|pipeline|automation|nodes?)\b",
    re.IGNORECASE,
)


def normalize_thread_messages(messages: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    """Keep role/content only for LLM history."""
    out: list[dict[str, str]] = []
    for msg in messages or []:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role") or "").strip().lower()
        if role not in {"user", "assistant"}:
            continue
        content = str(msg.get("content") or "").strip()
        if not content:
            continue
        out.append({"role": role, "content": content})
    return out


def _thread_has_actionable_footer(messages: list[dict[str, str]]) -> bool:
    """True when client thread includes a Sherpa sample-run or canvas-edit offer."""
    blob = "\n".join(str(m.get("content") or "") for m in messages)
    lower = blob.lower()
    if "**next step:**" in lower or "next step:" in lower:
        return True
    return "want me to start a sample run" in lower or "apply that change on the canvas" in lower


def _prefer_client_thread(
    normalized_client: list[dict[str, str]],
    existing: list[dict[str, str]],
) -> bool:
    """Prefer UI thread when it carries next-step footers the server summary omits."""
    if len(normalized_client) >= len(existing):
        return True
    if _thread_has_actionable_footer(normalized_client) and not _thread_has_actionable_footer(existing):
        return True
    client_chars = sum(len(str(m.get("content") or "")) for m in normalized_client)
    server_chars = sum(len(str(m.get("content") or "")) for m in existing)
    return client_chars > server_chars + 80


def resolve_thread_history(
    histories: dict[str, list[dict]],
    session_id: str | None,
    *,
    thread_messages: list[dict[str, Any]] | None = None,
    db_messages: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """Return prior turns for a session, hydrating from client or DB when needed."""
    if not session_id:
        return []

    normalized_client = normalize_thread_messages(thread_messages)
    if normalized_client:
        existing = histories.get(session_id) or []
        if _prefer_client_thread(normalized_client, existing):
            histories[session_id] = normalized_client
        return list(histories.get(session_id) or [])

    if session_id not in histories and db_messages:
        histories[session_id] = normalize_thread_messages(db_messages)

    return list(histories.setdefault(session_id, []))


def _truncate_thread_message(content: str, limit: int) -> str:
    """Trim long turns but keep the closing Next step / sample-run offer intact."""
    text = (content or "").strip()
    if len(text) <= limit:
        return text
    for marker in ("**Next step:**", "Next step:"):
        idx = text.rfind(marker)
        if idx < 0:
            continue
        suffix = text[idx:].strip()
        if len(suffix) <= max(limit // 2, 180):
            prefix_budget = max(120, limit - len(suffix) - 5)
            return text[:prefix_budget].rstrip() + "…\n\n" + suffix
    return text[:limit].rstrip() + "…"


def format_thread_context(
    history: list[dict[str, Any]] | None,
    *,
    max_turns: int = 8,
    max_chars: int = 5000,
    per_message_chars: int = 1800,
) -> str:
    """Compact recent chat turns for prompt / classifier injection."""
    if not history:
        return ""

    recent = history[-(max_turns * 2) :]
    lines: list[str] = []
    for msg in recent:
        role = str(msg.get("role") or "user").strip().lower()
        content = str(msg.get("content") or "").strip()
        if not content:
            continue
        if len(content) > per_message_chars:
            content = _truncate_thread_message(content, per_message_chars)
        label = "User" if role == "user" else "Sherpa"
        lines.append(f"{label}: {content}")

    text = "\n".join(lines).strip()
    if len(text) > max_chars:
        text = "…\n" + text[-max_chars:]
    return text


def append_thread_turn(
    histories: dict[str, list[dict]],
    session_id: str | None,
    *,
    user_message: str,
    assistant_message: str,
) -> None:
    """Record a completed copilot exchange in the in-memory thread cache."""
    if not session_id:
        return
    user_text = (user_message or "").strip()
    assistant_text = (assistant_message or "").strip()
    if not user_text and not assistant_text:
        return
    history = histories.setdefault(session_id, [])
    if user_text:
        history.append({"role": "user", "content": user_text})
    if assistant_text:
        history.append({"role": "assistant", "content": assistant_text})


def thread_references_recent_workflow(thread_context: str) -> bool:
    """Heuristic: prior turns mention a workflow the user may want to automate."""
    text = (thread_context or "").strip()
    if not text:
        return False
    return bool(_THREAD_ARTIFACT.search(text))
