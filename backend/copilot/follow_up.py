"""Follow-up message repair for multi-turn Sherpa edits."""
from __future__ import annotations

import re
from typing import Any

from copilot.next_action import (
    is_sample_run_next_step,
    last_next_step_from_thread,
    pending_action_from_thread,
)

# re-exported for enrich_route_metadata_for_follow_up

_TYPO_MAP = {
    "coomss": "comms_messages",
    "cooms": "comms_messages",
}

_EMAIL_TERMS = ("email", "mail", "outlook")

_ACTION_ACCEPTANCE_RE = re.compile(
    r"^(?:"
    r"do it|do that|do this|apply(?: it| that| this)?|fix it|make (?:that|the) change|"
    r"go ahead|yes(?: please)?|please do|implement(?: it| that| this)?|"
    r"update the workflow|change it|make it so|sounds good"
    r")\.?!?$",
    re.IGNORECASE,
)


def looks_like_action_acceptance(message: str) -> bool:
    """Short affirmatives that mean 'apply what you just suggested'."""
    text = (message or "").strip()
    if not text:
        return False
    lower = text.lower()
    if lower in ("eys", "yse", "ye", "yep", "yeah", "yup", "sure", "ok", "okay"):
        return True
    if _ACTION_ACCEPTANCE_RE.match(text):
        return True
    words = text.split()
    if len(words) <= 5 and re.search(r"\b(do it|do that|apply|fix it|yes|go ahead)\b", text.lower()):
        return True
    return False


def _workflow_name_from_thread(thread_context: str, canvas_workflow: dict[str, Any] | None) -> str | None:
    if canvas_workflow:
        name = str(canvas_workflow.get("name") or "").strip()
        if name:
            return name
    text = thread_context or ""
    for pattern in (
        r'["\']([^"\']{6,120})["\']',
        r"\*\*([^*]{6,120})\*\*",
        r"^([^\n]+?) Run Summary\b",
    ):
        match = re.search(pattern, text, re.MULTILINE)
        if match:
            candidate = match.group(1).strip()
            if candidate and "run summary" not in candidate.lower():
                return candidate
    return None


def extract_build_action_from_thread(
    thread_context: str,
    canvas_workflow: dict[str, Any] | None = None,
) -> str | None:
    """Turn the last assistant suggestion into a concrete build prompt."""
    text = (thread_context or "").strip()
    if not text:
        return None
    wf_name = _workflow_name_from_thread(text, canvas_workflow) or "the workflow on canvas"

    pending = pending_action_from_thread(text)
    if pending:
        return f"Apply to **{wf_name}** on the canvas: {pending}"

    lower = text.lower()
    if ("left join" in lower and "inner join" in lower) or (
        "configured" in lower and "left" in lower and "executed as an inner" in lower
    ):
        join_label = "Join Comms and Alerts"
        match = re.search(r"(Join[^\n(]+)\(", text, re.IGNORECASE)
        if match:
            join_label = match.group(1).strip()
        return (
            f"Edit **{wf_name}**: fix node **{join_label}** so `joinType` is `left` "
            f"and execution uses a left join (not inner). Keep all other nodes and outputs unchanged."
        )

    for marker in (
        "Suggested change to improve reliability:",
        "Reliability Improvement Suggestion:",
        "Action:",
        "Suggested change:",
    ):
        idx = text.rfind(marker)
        if idx >= 0:
            snippet = text[idx : idx + 600].strip()
            first_line = snippet.splitlines()[0]
            return (
                f"Apply this change to **{wf_name}** on the canvas: {first_line} "
                f"{_snip(snippet, 320)}"
            )

    if "ensure the join" in lower or "join type" in lower:
        return (
            f"Apply the join reliability fix discussed for **{wf_name}** — "
            f"use a left join as configured on the join node."
        )
    return None


def action_follow_up_outlook_unavailable_override(
    message: str,
    *,
    canvas_workflow: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """User cannot use Outlook — edit canvas to drop Outlook nodes, do not re-add them."""
    lower = (message or "").lower()
    if "outlook" not in lower:
        return None
    if not re.search(
        r"\b(not avail|not available|unavailable|can't use|cannot use|don't have|do not have|"
        r"remove|delete|without outlook|no outlook)\b",
        lower,
    ):
        return None
    if not canvas_workflow or not (canvas_workflow.get("nodes") or []):
        return None
    wf_name = str(canvas_workflow.get("name") or "the workflow on canvas").strip()
    return {
        "intent": "build",
        "reason": "User reported Outlook is unavailable — edit canvas to remove Outlook steps",
        "enhanced_question": (
            f"Edit **{wf_name}** on the canvas: remove every Outlook node and reconnect branches "
            f"so the pipeline completes without email. Do not add new Outlook nodes — Outlook is "
            f"not available in this environment."
        ),
        "metadata": {
            "edit_existing_workflow": True,
            "workflow_name": wf_name,
            "wants_outlook": False,
            "improvement_spec": {"requires": []},
        },
        "source": "follow_up_outlook",
    }


def action_follow_up_run_override(
    message: str,
    *,
    thread_context: str | None = None,
    canvas_workflow: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """When user accepts a sample-run offer ('yes'), flag wants_sample_run for the client."""
    if not looks_like_action_acceptance(message):
        return None
    action, question = last_next_step_from_thread(thread_context or "")
    if not is_sample_run_next_step(action, question):
        return None
    if not canvas_workflow and not _workflow_name_from_thread(thread_context or "", canvas_workflow):
        return None
    meta: dict[str, Any] = {"wants_sample_run": True, "edit_existing_workflow": False}
    wf_name = _workflow_name_from_thread(thread_context or "", canvas_workflow)
    if wf_name:
        meta["workflow_name"] = wf_name
    return {
        "intent": "ask",
        "reason": "User accepted the prior sample-run offer",
        "enhanced_question": (action or "Run the workflow on canvas with sample data").strip(),
        "metadata": meta,
        "source": "follow_up_run",
    }


def action_follow_up_create_build_override(
    message: str,
    *,
    thread_context: str | None = None,
    canvas_workflow: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """When user accepts a create-on-canvas offer after a build plan, run harness build."""
    if not looks_like_action_acceptance(message):
        return None
    from copilot.next_action import is_create_workflow_next_step

    step_action, step_question = last_next_step_from_thread(thread_context or "")
    if not is_create_workflow_next_step(step_action, step_question):
        return None
    wf_name = _workflow_name_from_thread(thread_context or "", canvas_workflow)
    original = ""
    for line in (thread_context or "").splitlines():
        if line.startswith("User:"):
            original = line.removeprefix("User:").strip()
    if not original:
        original = (step_action or "Create the workflow on the canvas").strip()
    meta: dict[str, Any] = {
        "build_plan_confirmed": True,
        "edit_existing_workflow": False,
        "propose_build_plan": False,
        "clarification_resolved": True,
    }
    if wf_name:
        meta["workflow_name"] = wf_name
    meta["original_user_request"] = original
    return {
        "intent": "build",
        "reason": "User confirmed creating the planned workflow on the canvas",
        "enhanced_question": original,
        "metadata": meta,
        "source": "follow_up_create_confirmed",
    }


def action_follow_up_build_override(
    message: str,
    *,
    thread_context: str | None = None,
    canvas_workflow: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """When user says 'do it', route to build instead of re-analyzing the run."""
    if not looks_like_action_acceptance(message):
        return None
    step_action, step_question = last_next_step_from_thread(thread_context or "")
    if is_sample_run_next_step(step_action, step_question):
        return None
    from copilot.next_action import is_canvas_edit_next_step as _is_canvas_edit

    if _is_canvas_edit(step_action, step_question) and step_action:
        wf_name = _workflow_name_from_thread(thread_context or "", canvas_workflow) or "the workflow on canvas"
        prompt = f"Apply to **{wf_name}** on the canvas: {step_action.strip().rstrip('.')}."
        if step_question:
            prompt += f" ({step_question.strip().rstrip('?')})"
        meta: dict[str, Any] = {"edit_existing_workflow": True}
        if wf_name:
            meta["workflow_name"] = wf_name
        return {
            "intent": "build",
            "reason": "User accepted the prior canvas-edit offer",
            "enhanced_question": prompt,
            "metadata": meta,
            "source": "follow_up",
        }
    action = extract_build_action_from_thread(thread_context or "", canvas_workflow)
    if not action:
        return None
    meta: dict[str, Any] = {"edit_existing_workflow": True}
    wf_name = _workflow_name_from_thread(thread_context or "", canvas_workflow)
    if wf_name:
        meta["workflow_name"] = wf_name
    return {
        "intent": "build",
        "reason": "User accepted the prior workflow fix suggestion",
        "enhanced_question": action,
        "metadata": meta,
        "source": "follow_up",
    }


def _snip(text: str, limit: int = 72) -> str:
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    return t[: limit - 1].rstrip() + "…"


def repair_follow_up_text(
    message: str,
    *,
    thread_context: str | None = None,
    canvas_workflow: dict[str, Any] | None = None,
) -> str:
    """Normalize typos and expand elliptical follow-ups using thread + canvas."""
    text = (message or "").strip()
    if not text:
        return text

    lower = text.lower()
    repaired = text

    for typo, replacement in _TYPO_MAP.items():
        if re.search(rf"\b{re.escape(typo)}\b", lower):
            repaired = re.sub(rf"\b{typo}\b", replacement, repaired, flags=re.IGNORECASE)

    if _looks_like_delta_edit(lower) and thread_context:
        prior_dataset = _prior_dataset(thread_context, canvas_workflow)
        if prior_dataset and prior_dataset not in repaired.lower():
            if "20" in lower and "comms_messages" in repaired.lower():
                repaired = (
                    f"{repaired} (limit to 20 rows from comms_messages joined or loaded "
                    f"alongside the existing {prior_dataset} workflow on canvas)"
                )
            elif any(t in lower for t in _EMAIL_TERMS):
                repaired = (
                    f"{repaired} (highlight or filter rows where channel or keyword "
                    f"suggests email, within the existing workflow)"
                )

    return repaired.strip()


def enrich_route_metadata_for_follow_up(
    metadata: dict[str, Any],
    *,
    message: str,
    thread_context: str | None = None,
    canvas_workflow: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Ensure edit follow-ups carry session context."""
    meta = dict(metadata or {})
    lower = (message or "").lower()
    pending_run = False
    if looks_like_action_acceptance(message) and thread_context:
        step_action, step_question = last_next_step_from_thread(thread_context)
        pending_run = is_sample_run_next_step(step_action, step_question)
    has_canvas = bool((canvas_workflow or {}).get("nodes"))
    if (
        meta.get("edit_existing_workflow")
        or (_looks_like_delta_edit(lower) and has_canvas)
        or (looks_like_action_acceptance(message) and not pending_run)
    ):
        meta["edit_existing_workflow"] = True
    if not meta.get("workflow_name") and canvas_workflow:
        name = str(canvas_workflow.get("name") or "").strip()
        if name:
            meta["workflow_name"] = name
    datasets = list(meta.get("session_datasets") or [])
    prior = _prior_dataset(thread_context or "", canvas_workflow)
    if prior and prior not in datasets:
        datasets.append(prior)
    if datasets:
        meta["session_datasets"] = datasets
    return meta


def _looks_like_delta_edit(lower: str) -> bool:
    return bool(
        re.search(r"\b(add|remove|delete|extend|highlight|also|fix|improve|wire|connect)\b", lower)
    )


def _prior_dataset(thread_context: str, canvas_workflow: dict[str, Any] | None) -> str | None:
    if canvas_workflow:
        for node in canvas_workflow.get("nodes") or []:
            if not isinstance(node, dict):
                continue
            cfg = node.get("config") or {}
            source = cfg.get("source")
            if source:
                return str(source)
    text = (thread_context or "").lower()
    for ds in ("leads.csv", "comms_messages", "hs_alerts"):
        if ds in text:
            return ds
    return None
