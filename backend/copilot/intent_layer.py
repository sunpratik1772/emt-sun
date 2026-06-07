"""Sherpa unified intent layer — thinking + disposition (plan | answer | clarify).

Every user message passes through this layer after coarse routing. It decides what
Sherpa should do next and whether clarifying questions are needed before acting.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from copilot.llm_router import SherpaRoute
from copilot.next_action import last_next_step_from_thread, parse_next_action_from_text
from llm import GeminiAdapter, gemini_configured, get_default_adapter

_DISPOSITIONS = frozenset({"plan", "answer", "clarify"})

_SHOW_FIX_PLAN_RE = re.compile(
    r"\b(?:ok(?:ay)?[,!\s]*)?(?:show|see|display|give)\s+(?:me\s+)?(?:the\s+)?(?:fix\s+)?plan\b",
    re.IGNORECASE,
)
_RUN_REVIEW_THREAD_RE = re.compile(
    r"\b(?:run summary|next step:|did not execute|reliability|run log)\b",
    re.IGNORECASE,
)
_BUILDISH_RE = re.compile(
    r"\b(create|build|make|generate|draft|add|extend|improve|fix|wire|connect|update the workflow)\b",
    re.IGNORECASE,
)

_INTENT_LAYER_SYSTEM = """You are Sherpa's intent understanding layer for dbSherpa Studio.

Given the user message, proposed route, studio context, node catalog, and data schema hints,
decide what Sherpa should do NEXT.

Return JSON only:
{
  "thinking": "2-4 short first-person lines separated by newlines — what you understand and will do",
  "disposition": "plan" | "answer" | "clarify",
  "confidence": 0.0-1.0,
  "reason": "one sentence",
  "clarify_questions": [
    {
      "id": "q1",
      "kind": "choice",
      "question": "question text",
      "options": [
        {"id": "a", "label": "Short label", "description": "helper under 120 chars"}
      ],
      "default_option_id": "a",
      "allow_multiple": false
    }
  ]
}

Disposition rules:
- plan: user wants a NEW workflow on canvas OR a numbered fix/extension plan before canvas changes.
  Use when building something new or extending existing workflow but steps are not yet concrete.
- answer: run review, platform Q&A, explain error, sample run, load, automate — respond directly.
- clarify: ONLY when disposition would be plan/build but critical inputs are missing.

Clarify rules (build / plan only):
- Ask 0 questions in JSON (empty clarify_questions) when the message + thread are sufficient.
- Ask 1+ questions only when node types, data sources, outputs, or scope are genuinely unknown.
- Scale question count to uncertainty: vague one-liner → up to 3; partially specified → 1-2; detailed → 0.
- Challenge vague terms against node catalog and schema (grill-me style): propose precise options.
- Do NOT ask clarifying questions for explain_run, sample runs, or clear edit follow-ups.
- Do NOT include id=other in options — the UI adds "Something else" last.
- kind=confirm for yes/no; kind=choice for mutually exclusive or multi-select options.

Thinking style: engineer thinking out loud — never echo "User asked:" or route chip text verbatim."""


@dataclass
class SherpaDisposition:
    kind: str  # plan | answer | clarify
    thinking: str = ""
    confidence: float = 1.0
    reason: str = ""
    clarify_questions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "thinking": self.thinking,
            "confidence": self.confidence,
            "reason": self.reason,
            "clarify_questions": list(self.clarify_questions),
        }


def _extract_json(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass
    start = raw.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(raw)):
        ch = raw[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    parsed = json.loads(raw[start : i + 1])
                    return parsed if isinstance(parsed, dict) else None
                except Exception:
                    return None
    return None


def _canvas_node_types(canvas_workflow: dict[str, Any] | None) -> set[str]:
    types: set[str] = set()
    for n in (canvas_workflow or {}).get("nodes") or []:
        if isinstance(n, dict) and n.get("type"):
            types.add(str(n["type"]))
    return types


def _canvas_datasets(canvas_workflow: dict[str, Any] | None) -> list[str]:
    out: list[str] = []
    for n in (canvas_workflow or {}).get("nodes") or []:
        if not isinstance(n, dict):
            continue
        cfg = n.get("config") or {}
        for key in ("source", "path", "filename", "table", "query"):
            val = str(cfg.get(key) or "").strip()
            if val and val not in out:
                out.append(val)
    return out[:8]


def _node_catalog_context(canvas_workflow: dict[str, Any] | None) -> str:
    try:
        from copilot.run_analyst import _node_catalog_slice

        types = _canvas_node_types(canvas_workflow)
        if not types:
            from engine.studio_nodes import STUDIO_APPROVED_NODE_TYPES

            types = set(STUDIO_APPROVED_NODE_TYPES)  # type: ignore[arg-type]
        catalog = _node_catalog_slice(types)[:24]
        return json.dumps(catalog, default=str)[:2400]
    except Exception:
        return "[]"


def build_fix_plan_ask_prompt(
    *,
    workflow_name: str | None,
    fix_action: str | None,
    user_message: str,
) -> str:
    """Numbered remediation plan after a run review — no canvas rebuild."""
    name = (workflow_name or "the workflow").strip()
    action = (fix_action or "the reliability issue from the run review").strip().rstrip(".")
    return "\n".join(
        [
            "Plan only — user wants a numbered FIX plan from the prior run review. Do NOT rebuild or draft the workflow.",
            f"Workflow: **{name}**",
            f"User message: {user_message.strip() or '(show the plan)'}",
            f"Focus the plan on: {action}",
            "",
            "Respond with:",
            "1. One short sentence ending with exactly: Below is the plan.",
            "2. A numbered PLAN (3–6 concrete steps) to fix wiring, config, or execution — cite node labels when known.",
            "3. Do NOT claim you built or changed the canvas.",
            "4. Do NOT add **Next step:** footers or sample-run offers.",
        ]
    )


def action_follow_up_show_fix_plan_override(
    message: str,
    *,
    thread_context: str | None = None,
    canvas_workflow: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """After run review, 'show the plan' means a fix plan — not harness rebuild."""
    text = (message or "").strip()
    if not _SHOW_FIX_PLAN_RE.search(text):
        return None
    thread = thread_context or ""
    if not _RUN_REVIEW_THREAD_RE.search(thread):
        return None
    from copilot.follow_up import _workflow_name_from_thread

    wf_name = _workflow_name_from_thread(thread, canvas_workflow)
    assistant = ""
    for line in thread.splitlines():
        if line.startswith("Sherpa:"):
            assistant = line.removeprefix("Sherpa:").strip()
    action, _question = parse_next_action_from_text(assistant) if assistant else (None, None)
    if not action:
        action, _ = last_next_step_from_thread(thread)
    prompt = build_fix_plan_ask_prompt(
        workflow_name=wf_name,
        fix_action=action,
        user_message=text,
    )
    meta: dict[str, Any] = {
        "propose_fix_plan": True,
        "propose_build_plan": True,
        "edit_existing_workflow": True,
        "build_plan_confirmed": False,
        "original_user_request": text,
    }
    if wf_name:
        meta["workflow_name"] = wf_name
    return {
        "intent": "ask",
        "reason": "User wants a numbered fix plan from the prior run review",
        "enhanced_question": prompt,
        "metadata": meta,
        "source": "follow_up_show_fix_plan",
    }


def _heuristic_disposition(
    route: SherpaRoute,
    message: str,
    *,
    thread_context: str | None,
    has_workflow: bool,
    canvas_workflow: dict[str, Any] | None,
) -> SherpaDisposition | None:
    """Fast disposition without LLM when the next action is obvious."""
    meta = dict(route.metadata or {})
    intent = str(route.intent or "")
    text = (message or "").strip()
    lower = text.lower()

    if meta.get("build_plan_confirmed"):
        return SherpaDisposition(
            kind="answer",
            thinking="I'll build the approved workflow on the canvas.\n"
            "Mapping sources, transforms, and outputs from the plan.\n"
            "Starting the harness build now.",
            confidence=0.95,
            reason="User approved the build plan — execute on canvas.",
        )

    if meta.get("propose_fix_plan"):
        return SherpaDisposition(
            kind="plan",
            thinking="I'll lay out a numbered fix plan from the run review.\n"
            "Focusing on the node that skipped and its wiring.\n"
            "Drafting the plan now.",
            confidence=0.95,
            reason="Fix plan requested after run review.",
        )

    if meta.get("propose_build_plan"):
        return SherpaDisposition(
            kind="plan",
            thinking="I'll draft a concrete pipeline plan before touching the canvas.\n"
            "Mapping sources, transforms, and outputs from your request.\n"
            "Drafting the plan now.",
            confidence=0.9,
            reason="New workflow build requires plan-first.",
        )

    if meta.get("wants_sample_run"):
        return SherpaDisposition(
            kind="answer",
            thinking="I'll run the workflow with sample data.\n"
            "Then summarize output and any failures.\n"
            "Starting the sample run now.",
            confidence=0.95,
            reason="Sample run execution.",
        )

    if intent in ("explain_run", "explain_error", "query_run_data"):
        return SherpaDisposition(
            kind="answer",
            thinking="I'll pull the latest run log and scan each step.\n"
            "Checking row counts, skipped nodes, and export artifacts.\n"
            "Writing the run summary now.",
            confidence=0.92,
            reason="Run analysis proceeds directly.",
        )

    if intent == "load":
        return SherpaDisposition(
            kind="answer",
            thinking="I'll find the saved workflow and load it onto the canvas.\n"
            "Matching the name from your message.\n"
            "Loading now.",
            confidence=0.88,
            reason="Load workflow onto canvas.",
        )

    if intent == "automate":
        return SherpaDisposition(
            kind="answer",
            thinking="I'll set up the schedule and wire it to the workflow.\n"
            "Checking cron and trigger settings.\n"
            "Drafting the automation now.",
            confidence=0.88,
            reason="Automation setup.",
        )

    if intent == "ask" and not meta.get("propose_build_plan"):
        return SherpaDisposition(
            kind="answer",
            thinking="I'll answer from Studio docs and the current canvas context.\n"
            "Pulling node types and workflow state as needed.\n"
            "Drafting the answer now.",
            confidence=0.85,
            reason="Platform Q&A.",
        )

    if intent == "build":
        if meta.get("build_plan_confirmed"):
            return SherpaDisposition(
                kind="answer",
                thinking="I'll build the approved workflow on the canvas.\n"
                "Tracing the plan steps into nodes and edges.\n"
                "Starting the harness build now.",
                confidence=0.95,
                reason="Approved build — run harness.",
            )
        edit = bool(meta.get("edit_existing_workflow") or has_workflow or (canvas_workflow or {}).get("nodes"))
        detailed = len(text) > 80 or bool(meta.get("clarification_resolved"))
        if edit and detailed:
            return SherpaDisposition(
                kind="answer",
                thinking="I'll apply the requested change on the canvas workflow.\n"
                "Tracing edges and node config before editing.\n"
                "Drafting now.",
                confidence=0.88,
                reason="Concrete canvas edit.",
            )
        if not edit and len(text) < 45 and not detailed:
            return SherpaDisposition(
                kind="clarify",
                thinking="The build request is still vague.\n"
                "I need sources, transforms, and output format before planning.\n"
                "Preparing clarifying questions.",
                confidence=0.55,
                reason="Short new-build request lacks concrete pipeline detail.",
            )
        if not edit:
            return SherpaDisposition(
                kind="plan",
                thinking="I'll draft a pipeline plan before creating on the canvas.\n"
                "Mapping data sources and export steps from your request.\n"
                "Drafting the plan now.",
                confidence=0.8,
                reason="New workflow build.",
            )

    if _BUILDISH_RE.search(lower) and len(text) < 50:
        return SherpaDisposition(
            kind="clarify",
            thinking="I need a bit more detail before I can plan this pipeline.\n"
            "Checking which sources and outputs you mean.\n"
            "Preparing clarifying questions.",
            confidence=0.5,
            reason="Build-ish message without enough pipeline detail.",
        )

    return None


def _disposition_from_router_meta(meta: dict[str, Any]) -> SherpaDisposition | None:
    """Use disposition bundled in the main router response — skips a second LLM call."""
    kind = str(meta.get("router_disposition") or meta.get("sherpa_disposition") or "").strip().lower()
    if kind not in _DISPOSITIONS:
        return None
    thinking = str(meta.get("router_thinking") or meta.get("thinking_preview") or "").strip()
    questions = meta.get("router_clarify_questions") or []
    if not isinstance(questions, list):
        questions = []
    if kind == "clarify" and not questions:
        kind = "plan"
    return SherpaDisposition(
        kind=kind,
        thinking=thinking,
        confidence=float(meta.get("disposition_confidence") or 0.82),
        reason="Router disposition",
        clarify_questions=[q for q in questions if isinstance(q, dict)] if kind == "clarify" else [],
    )


def _llm_disposition(
    route: SherpaRoute,
    message: str,
    *,
    thread_context: str | None,
    has_workflow: bool,
    canvas_workflow: dict[str, Any] | None,
    adapter: GeminiAdapter | None = None,
) -> SherpaDisposition | None:
    if not gemini_configured() and adapter is None:
        return None
    meta = dict(route.metadata or {})
    datasets = _canvas_datasets(canvas_workflow)
    user_turn = "\n".join(
        [
            f"User message:\n{message}",
            f"Proposed route: intent={route.intent} reason={route.reason}",
            f"enhanced_question={route.enhanced_question}",
            f"metadata={json.dumps(meta, default=str)[:1200]}",
            f"has_workflow={has_workflow}",
            f"canvas_datasets={datasets}",
            f"node_catalog={_node_catalog_context(canvas_workflow)}",
            f"Thread (recent):\n{(thread_context or '')[-2800:]}",
        ]
    )
    try:
        raw = (adapter or get_default_adapter()).chat_turn(
            system_prompt=_INTENT_LAYER_SYSTEM,
            history=[],
            user_turn=user_turn,
            temperature=0.0,
            json_mode=True,
        )
        parsed = _extract_json(raw) or {}
    except Exception:
        return None

    kind = str(parsed.get("disposition") or "answer").strip().lower()
    if kind not in _DISPOSITIONS:
        kind = "answer"
    thinking = str(parsed.get("thinking") or "").strip()
    questions = parsed.get("clarify_questions") or []
    if not isinstance(questions, list):
        questions = []
    if kind == "clarify" and not questions:
        kind = "plan" if str(route.intent) == "build" else "answer"
    if kind != "clarify":
        questions = []
    return SherpaDisposition(
        kind=kind,
        thinking=thinking,
        confidence=float(parsed.get("confidence") or 0.75),
        reason=str(parsed.get("reason") or "Intent layer assessment"),
        clarify_questions=[q for q in questions if isinstance(q, dict)],
    )


def _advisory_answer_disposition(message: str) -> SherpaDisposition | None:
    """Platform how-to / exploratory questions always answer — never clarify."""
    from copilot.run_output_questions import is_run_output_question
    from generation.harness.intent import is_advisory_question_heuristic

    if is_run_output_question(message) or not is_advisory_question_heuristic(message):
        return None
    return SherpaDisposition(
        kind="answer",
        thinking="I'll answer from Studio docs and the current canvas context.\n"
        "Pulling node types and workflow state as needed.\n"
        "Drafting the answer now.",
        confidence=0.92,
        reason="Platform how-to / advisory question.",
    )


def resolve_sherpa_disposition(
    route: SherpaRoute,
    message: str,
    *,
    thread_context: str | None = None,
    has_workflow: bool = False,
    canvas_workflow: dict[str, Any] | None = None,
    adapter: GeminiAdapter | None = None,
) -> tuple[SherpaRoute, SherpaDisposition]:
    """Apply intent-layer overrides and return (possibly adjusted route, disposition)."""
    fix_override = action_follow_up_show_fix_plan_override(
        message,
        thread_context=thread_context,
        canvas_workflow=canvas_workflow,
    )
    if fix_override:
        merged_meta = {**(route.metadata or {}), **fix_override.get("metadata", {})}
        route = SherpaRoute(
            intent=str(fix_override["intent"]),
            reason=str(fix_override.get("reason") or route.reason),
            enhanced_question=str(fix_override.get("enhanced_question") or route.enhanced_question),
            keywords=route.keywords,
            metadata=merged_meta,
            source=str(fix_override.get("source") or "intent_layer"),
        )

    meta = dict(route.metadata or {})
    if meta.get("edit_existing_workflow") and not has_workflow:
        meta["edit_existing_workflow"] = False
        route = SherpaRoute(
            intent=route.intent,
            reason=route.reason,
            enhanced_question=route.enhanced_question,
            keywords=route.keywords,
            metadata=meta,
            source=route.source,
        )
    advisory_disp = (
        None
        if meta.get("clarification_resolved") or meta.get("edit_existing_workflow")
        else _advisory_answer_disposition(message)
    )
    if advisory_disp is not None and str(route.intent) == "build":
        route = SherpaRoute(
            intent="ask",
            reason=route.reason,
            enhanced_question=route.enhanced_question,
            keywords=route.keywords,
            metadata=meta,
            source=route.source,
        )
    heuristic = _heuristic_disposition(
        route,
        message,
        thread_context=thread_context,
        has_workflow=has_workflow,
        canvas_workflow=canvas_workflow,
    )
    router_disp = _disposition_from_router_meta(meta)
    strong_heuristic = heuristic is not None and (
        meta.get("propose_fix_plan")
        or meta.get("propose_build_plan")
        or meta.get("wants_sample_run")
        or str(route.intent) in ("explain_run", "explain_error", "load", "automate")
        or heuristic.kind == "clarify"
        or advisory_disp is not None
    )
    if advisory_disp is not None:
        disposition = advisory_disp
    elif strong_heuristic:
        disposition = heuristic
    elif router_disp is not None:
        disposition = router_disp
    elif heuristic is not None:
        disposition = heuristic
    else:
        disposition = None

    if disposition is None:
        llm_disp = _llm_disposition(
            route,
            message,
            thread_context=thread_context,
            has_workflow=has_workflow,
            canvas_workflow=canvas_workflow,
            adapter=adapter,
        )
        disposition = llm_disp or SherpaDisposition(
            kind="answer",
            thinking="I'll work from your message and the current studio context.\n"
            "Checking workflow and run state first.\n"
            "Drafting now.",
            confidence=0.7,
            reason="Default answer disposition.",
        )

    # Canvas edits execute directly — not plan-first (unless fix-plan flow).
    if (
        str(route.intent) == "build"
        and meta.get("edit_existing_workflow")
        and has_workflow
        and not meta.get("propose_build_plan")
        and not meta.get("propose_fix_plan")
    ):
        disposition = SherpaDisposition(
            kind="answer",
            thinking=disposition.thinking
            or "I'll apply the requested change on the canvas workflow.\n"
            "Tracing edges and node config before editing.\n"
            "Drafting now.",
            confidence=max(disposition.confidence, 0.88),
            reason="Concrete canvas edit — execute without plan gate.",
        )

    meta["sherpa_disposition"] = disposition.kind
    meta["disposition_confidence"] = disposition.confidence
    if disposition.thinking:
        meta["thinking_preview"] = disposition.thinking
    if disposition.kind != "clarify":
        meta.pop("intent_layer_clarify", None)
        meta.pop("intent_layer_questions", None)
        meta.pop("intent_layer_clarify_reason", None)
        meta.pop("router_clarify_questions", None)

    # Clarify only for unclear build/plan paths
    if disposition.kind == "clarify":
        if disposition.clarify_questions:
            meta["intent_layer_clarify"] = True
            meta["intent_layer_questions"] = disposition.clarify_questions
            meta["intent_layer_clarify_reason"] = disposition.reason
        elif str(route.intent) == "build" and not meta.get("edit_existing_workflow"):
            meta["propose_build_plan"] = True
            disposition = SherpaDisposition(
                kind="plan",
                thinking=disposition.thinking
                or "I'll draft a pipeline plan before creating on the canvas.\n"
                "Filling in missing details from your request.\n"
                "Drafting the plan now.",
                confidence=max(disposition.confidence, 0.65),
                reason="Unclear build — plan-first instead of blocking clarify.",
            )
            meta["sherpa_disposition"] = "plan"
    elif disposition.kind == "plan" and str(route.intent) == "build" and not meta.get("edit_existing_workflow"):
        if (
            not meta.get("propose_build_plan")
            and not meta.get("propose_fix_plan")
            and not meta.get("build_plan_confirmed")
        ):
            meta["propose_build_plan"] = True

    return (
        SherpaRoute(
            intent=route.intent,
            reason=disposition.reason or route.reason,
            enhanced_question=route.enhanced_question,
            keywords=route.keywords,
            metadata=meta,
            source=route.source,
        ),
        disposition,
    )
