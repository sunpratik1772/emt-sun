"""Copilot workflow load — search saved workflows and load or disambiguate."""
from __future__ import annotations

import re
from typing import Any, Iterator

from app.database import list_workflow_library_rows
from app.workflow_search import search_workflows

_LOAD_PREFIX = re.compile(
    r"^(?:please\s+)?(?:can you\s+)?(?:could you\s+)?"
    r"(?:load|open|find|show me|get|pull up|switch to)\s+"
    r"(?:the\s+)?(?:saved\s+)?(?:workflow\s+)?",
    re.IGNORECASE,
)
_LOAD_SUFFIX = re.compile(r"\s+workflow\s*[.?!]*$", re.IGNORECASE)


def is_load_workflow_request(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    lower = text.lower()
    if re.search(
        r"\b(load|open|find|pull up|switch to|show me)\b"
        r'(?:.{0,48}\b(workflow|pipeline)\b|.{0,28}(?:"[^"]{3,120}"|\'[^\']{3,120}\')|.{0,36}\bonto the canvas\b)',
        lower,
    ):
        return True
    if re.search(r"^load\s+\w", lower) and not re.search(r"\b(create|build|make|generate)\b", lower):
        return True
    return False


def extract_workflow_search_query(message: str) -> str:
    text = (message or "").strip()
    quoted = re.search(r'["\']([^"\']{3,120})["\']', text)
    if quoted:
        return quoted.group(1).strip()
    text = _LOAD_PREFIX.sub("", text).strip()
    text = re.sub(r"\s+onto the canvas\s*[.?!]*$", "", text, flags=re.IGNORECASE).strip()
    text = _LOAD_SUFFIX.sub("", text).strip()
    return text or (message or "").strip()


def run_workflow_load_stream(message: str) -> Iterator[dict[str, Any]]:
    """Yield SSE frames for load / disambiguate / not_found."""
    from copilot.thinking_monologue import ThinkingMonologueContext
    from copilot.next_action import ensure_load_next_action_footer
    from copilot.thinking_sse import yield_llm_thinking_monologue

    query = extract_workflow_search_query(message)
    ctx = ThinkingMonologueContext.for_load(message, query=query)
    yield from yield_llm_thinking_monologue(ctx)

    from app.request_context import get_current_user_id

    rows = list_workflow_library_rows(get_current_user_id())
    result = search_workflows(rows, query, limit=3)

    action = result.get("action")
    if action == "load":
        match = result.get("match") or {}
        workflow = result.get("workflow") or {}
        name = str(match.get("name") or workflow.get("name") or "Workflow")
        node_count = len(workflow.get("nodes") or [])
        yield {
            "type": "workflow_created",
            "workflowId": str(workflow.get("workflow_id") or match.get("workflow_id") or ""),
            "name": name,
            "nodeCount": node_count,
            "workflow": workflow,
        }
        reply = ensure_load_next_action_footer(
            f"Loaded **{name}** ({node_count} nodes) onto the canvas.",
            query=query,
            loaded_name=name,
            found=True,
        )
        yield {"type": "text_start"}
        yield {"type": "text_chunk", "chunk": reply}
        yield {"type": "text_end"}
        yield {"type": "done", "success": True, "intent": "load_workflow"}
        return

    if action == "disambiguate":
        matches = result.get("matches") or []
        lines = [result.get("message") or "I found a few likely matches:"]
        for i, m in enumerate(matches, start=1):
            label = m.get("name") or m.get("filename")
            lines.append(f"{i}. **{label}** (`{m.get('filename')}`)")
        lines.append("\nReply with the number or name to load one.")
        reply = ensure_load_next_action_footer(
            "\n".join(lines),
            query=query,
            found=False,
        )
        yield {
            "type": "workflow_disambiguation",
            "query": query,
            "matches": matches,
        }
        yield {"type": "text_start"}
        yield {"type": "text_chunk", "chunk": reply}
        yield {"type": "text_end"}
        yield {"type": "done", "success": True, "intent": "load_workflow"}
        return

    reply = ensure_load_next_action_footer(
        (
            f"I couldn't find a saved or draft workflow matching **{query}**. "
            "Try a different name, or ask me to build a new pipeline."
        ),
        query=query,
        found=False,
    )
    yield {"type": "text_start"}
    yield {"type": "text_chunk", "chunk": reply}
    yield {"type": "text_end"}
    yield {"type": "done", "success": False, "intent": "load_workflow"}
