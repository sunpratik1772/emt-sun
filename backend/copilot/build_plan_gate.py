"""Gate new workflow creation: plan + confirm before harness build."""
from __future__ import annotations

import re
from typing import Any

from copilot.llm_router import SherpaRoute
from copilot.next_action import format_next_action_block, strip_next_action_block

_PLAN_STEP_RE = re.compile(r"(?m)^\s*\d+[.)]\s+\S")
_PLAN_HEADER_RE = re.compile(r"\b(?:numbered\s+)?plan\b", re.IGNORECASE)

PLAN_APPROVAL_QUESTION_ID = "q_plan_approve"

_PLAN_ONLY_MARKERS = (
    "plan only",
    "do not build",
    "not create anything",
    "until they confirm",
)


def build_plan_ask_prompt(
    user_request: str,
    *,
    workflow_name: str | None = None,
    clarification: str | None = None,
) -> str:
    """System-facing ask prompt: plan + spec questions, no canvas build."""
    original = (user_request or "").strip()
    clar = (clarification or "").strip()
    name = (workflow_name or "").strip()
    parts = [
        "Plan only — the user wants a NEW workflow on the canvas. You must NOT build, draft, or load anything yet.",
        f"Original request:\n{original or '(see clarification)'}",
    ]
    if clar:
        parts.append(f"User clarification:\n{clar}")
    if name:
        parts.append(f"Target workflow name: **{name}**")
    parts.extend(
        [
            "",
            "Respond with:",
            "1. One short sentence ending with exactly: Below is the plan.",
            "2. Then a numbered PLAN (3–6 concrete pipeline steps) OR labeled steps (e.g. Load Data: …).",
            "   The UI shows steps only in the approval panel — still output them after the opening sentence.",
            "3. If inputs are vague, ask what to specify (sources, filters, outputs) in one line before the plan.",
            "4. Do NOT add **Next step:** footers, 'Should I create', or any create-on-canvas confirmation.",
            "5. Do NOT claim you built or drafted the workflow.",
        ]
    )
    return "\n".join(parts)


def has_build_plan_content(text: str) -> bool:
    """True when assistant text contains a concrete numbered plan (not just a footer)."""
    body = strip_next_action_block((text or "").strip())
    if not body or len(body) < 40:
        return False
    step_matches = list(_PLAN_STEP_RE.finditer(body))
    if len(step_matches) >= 2:
        return True
    if len(step_matches) == 1 and _PLAN_HEADER_RE.search(body):
        return True
    return False


def message_requests_build_plan(message: str, *, propose_build_plan: bool = False) -> bool:
    if propose_build_plan:
        return True
    lower = (message or "").lower()
    return any(m in lower for m in _PLAN_ONLY_MARKERS)


def ensure_build_plan_confirm_footer(
    text: str,
    *,
    workflow_name: str | None = None,
) -> str:
    """Append a create-on-canvas confirm offer after a plan-only ask reply."""
    body = strip_next_action_block((text or "").strip())
    if not body:
        return body
    name = (workflow_name or "the workflow").strip()
    block = format_next_action_block(
        f"Create **{name}** on the canvas from the plan above",
        f"Should I create **{name}** on the canvas now",
    )
    return f"{body}\n\n{block}"


def gate_route_to_build_plan_phase(route: SherpaRoute, message: str) -> SherpaRoute:
    """Redirect new-workflow builds to ask/plan until the user confirms."""
    meta = dict(route.metadata or {})
    if meta.get("build_plan_confirmed"):
        return route
    if meta.get("propose_build_plan"):
        if route.intent == "build":
            return SherpaRoute(
                intent="ask",
                reason=route.reason or "Build plan phase",
                enhanced_question=route.enhanced_question or build_plan_ask_prompt(
                    meta.get("original_user_request") or message,
                    workflow_name=meta.get("workflow_name"),
                ),
                keywords=route.keywords,
                metadata=meta,
                source=route.source or "build_plan_gate",
            )
        return route
    if route.intent != "build":
        return route
    if meta.get("edit_existing_workflow"):
        return route
    if meta.get("slash_route"):
        return route
    if str(route.source or "").startswith("clarification_confirmed_build"):
        return route

    original = (meta.get("original_user_request") or message or "").strip()
    meta["propose_build_plan"] = True
    meta["build_plan_confirmed"] = False
    meta["original_user_request"] = original
    wf_name = str(meta.get("workflow_name") or "").strip() or None
    if not wf_name:
        match = re.search(r'["\']([^"\']{4,120})["\']', original)
        if match:
            wf_name = match.group(1).strip()

    return SherpaRoute(
        intent="ask",
        reason="Present a build plan before creating on the canvas",
        enhanced_question=build_plan_ask_prompt(original, workflow_name=wf_name),
        keywords=route.keywords,
        metadata=meta,
        source="build_plan_gate",
    )
