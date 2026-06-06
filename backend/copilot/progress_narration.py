"""User-facing progress copy for Sherpa generation timeline events."""
from __future__ import annotations

import re

from generation.harness.state import AgentEvent, AgentPhase

# UI detail — complete sentences only; clip at sentence boundaries.
_CLIP = 320

_PARALLEL_TITLE_MAP = {
    "dataset and schema plan": "Checking data sources",
    "topology and action plan": "Designing workflow steps",
    "output artifact plan": "Planning export",
    "data access plan": "Checking data sources",
    "topology plan": "Designing workflow steps",
}


def _ensure_sentence(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return t
    if t[-1] in ".!?":
        return t
    return f"{t}."


def _clip_sentences(text: str, limit: int = _CLIP) -> str:
    t = (text or "").strip()
    if not t:
        return t
    if len(t) <= limit:
        return _ensure_sentence(t)
    chunk = t[:limit]
    best = -1
    for sep in (". ", ".\n", "! ", "? "):
        idx = chunk.rfind(sep)
        if idx > 48 and idx > best:
            best = idx + len(sep.rstrip())
    if best > 0:
        return chunk[:best].strip()
    return _ensure_sentence(chunk.rstrip(" ,;:") + "…")


def _sanitize_user_copy(text: str) -> str:
    """Strip harness jargon; keep plain-language progress."""
    t = (text or "").strip()
    if not t:
        return t
    t = re.sub(r"\bNOT NULL\b", "required fields", t, flags=re.IGNORECASE)
    t = re.sub(r"\bdb_query\b", "data load", t, flags=re.IGNORECASE)
    t = re.sub(r"\bcontract-backed fields\b", "supported columns", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+", " ", t)
    return _clip_sentences(t)


def user_facing_parallel_title(name: str) -> str:
    raw = (name or "").strip()
    if not raw:
        return "Planning"
    mapped = _PARALLEL_TITLE_MAP.get(raw.lower())
    return mapped or raw


def stage_title(event: AgentEvent, *, db_name: str = "Database") -> str:
    """Short milestone title shown as the step heading."""
    data = event.data or {}
    subagent = (data.get("subagent_name") or "").strip()
    if subagent:
        return user_facing_parallel_title(subagent)

    label = (event.label or "").strip()
    if not label:
        return _PHASE_TITLES.get(event.phase, "Working")

    key = label.lower()
    if key == "dispatch_parallel_tasks":
        return "Planning workflow"
    if key == "collect_parallel_results":
        return "Combining plans"
    if key == "matched_blueprint":
        return "Matched studio blueprint"
    if key == "parallel_subagent":
        return user_facing_parallel_title(event.detail or "Planning")
    if label == "Understanding the request":
        return "Understanding your request"
    if label == "Retrieving context":
        return "Loading studio context"
    if label == "Creating nodes & edges":
        return "Drafting workflow"
    if label.startswith("Repair pass"):
        return label
    if label == "Deterministic auto-fix":
        return "Applying automatic fixes"
    if label == "Runtime smoke test":
        return "Running test execution"
    if label == "Finalizing workflow":
        return "Finalizing workflow"
    return label


def progress_description(event: AgentEvent) -> str:
    """What is happening or what was completed — shown under the step title."""
    data = event.data or {}
    detail = _sanitize_user_copy((event.detail or "").strip())

    if event.status == "running":
        if detail:
            return detail
        return _running_default(event)

    if event.status == "error":
        return _sanitize_user_copy(detail or "This step failed.")

    outcome = data.get("outcome")
    if isinstance(outcome, str) and outcome.strip():
        return _sanitize_user_copy(outcome.strip())
    if detail:
        return detail
    return _done_default(event)


def _running_default(event: AgentEvent) -> str:
    label = (event.label or "").lower()
    if label == "creating nodes & edges":
        return "Drafting nodes, connections, and configuration."
    if label == "runtime smoke test":
        return "Running a quick sample execution to verify the workflow."
    if label.startswith("repair pass"):
        return "Fixing validation or runtime issues from the last attempt."
    if "parallel" in label or event.data.get("subagent_type"):
        return "Working through this part of the plan."
    if label == "dispatch_parallel_tasks":
        return "Breaking the request into parallel planning tasks."
    if label == "collect_parallel_results":
        return "Merging parallel planning results."
    return "In progress."


def _done_default(event: AgentEvent) -> str:
    label = (event.label or "").lower()
    if label == "creating nodes & edges":
        return "Workflow structure is ready."
    if label == "runtime smoke test":
        return "Test run completed successfully."
    if label.startswith("repair pass"):
        return "Repair attempt finished."
    if event.data.get("subagent_type") or label == "parallel_subagent":
        return "Planning step completed."
    return "Done."


_PHASE_TITLES: dict[AgentPhase, str] = {
    AgentPhase.UNDERSTANDING: "Understanding request",
    AgentPhase.RETRIEVING: "Loading context",
    AgentPhase.PLANNING: "Planning",
    AgentPhase.GENERATING: "Generating workflow",
    AgentPhase.AUTO_FIXING: "Auto-fixing",
    AgentPhase.CRITIQUING: "Repairing",
    AgentPhase.FINALIZING: "Finalizing",
    AgentPhase.ERROR: "Error",
    AgentPhase.COMPLETE: "Complete",
}
