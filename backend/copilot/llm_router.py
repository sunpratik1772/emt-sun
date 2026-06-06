"""Sherpa LLM router — structured intent + enhanced question + metadata."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from llm import GeminiAdapter, gemini_configured, get_default_adapter

_ROUTE_SYSTEM = """You route messages for dbSherpa Studio (Sherpa workflow builder).

Return JSON only with this exact shape:
{
  "intent": "build"|"ask"|"automate"|"load"|"explain_run"|"explain_error"|"query_run_data",
  "reason": "one short sentence",
  "enhanced_question": "clear normalized question for the downstream handler",
  "thinking": "2-4 short first-person lines (newline-separated) — what you understand and will do next",
  "disposition": "plan"|"answer"|"clarify",
  "confidence": 0.0-1.0,
  "clarify_questions": [],
  "keywords": ["keyword1", "keyword2"],
  "metadata": {
    "workflow_name": null,
    "run_selector": null,
    "run_id": null,
    "run_status_filter": null,
    "error_message": null,
    "node_id": null,
    "topics": [],
    "wants_sql": false,
    "edit_existing_workflow": false,
    "verification_plan": null,
    "wants_outlook": false,
    "wants_validation": false
  }
}

Intent rules:
- build: create, edit, fix, extend, or IMPROVE a workflow on the canvas (no schedule).
  When the user names a saved workflow and asks to improve/add/extend it, set metadata.edit_existing_workflow true
  and metadata.workflow_name. In enhanced_question, list EVERY requested addition explicitly (validation node,
  condition with true/false branches for failures, outlook node for completion summary, etc.).
- load: open/find/load an EXISTING saved workflow by name
- automate: schedule, cron, daily runs, create automation
- ask: platform Q&A (skills, nodes, integrations) WITHOUT analyzing a specific run
- explain_run: analyze/review/summarize a workflow RUN or its output (row counts, traders, reliability)
- explain_error: diagnose why a run or node FAILED
- query_run_data: user wants SQL/tabular analysis on run output data

For explain_run / explain_error / query_run_data:
- Extract workflow_name from quotes or context when mentioned
- run_selector: "latest" when user says latest/last/most recent run; "current" when referring to the run just executed on canvas; null otherwise
- enhanced_question must be self-contained (downstream LLM will not see the raw user message)
- verification_plan: when the question involves counts, rankings, comparisons, reliability, or verification,
  set a list of check ids such as "row_counts", "join_orphans" (for reliability/join questions use both).
  Set wants_sql true when verification_plan is populated. Do not emit suggested_sql — verification runs in Python.

Prefer explain_run over ask when the user discusses run output, reliability, row counts, or ranked results.
Prefer explain_error when failures, errors, or broken nodes are central.
Prefer build when concrete pipeline steps are requested without run analysis.
When the user affirms a prior assistant suggestion ("do it", "apply that", "fix it", "yes", "go ahead"),
check the prior Sherpa **Next step:** offer. If it offered a sample run, set intent=ask and
metadata.wants_sample_run=true (do not rebuild). Otherwise route to build with
metadata.edit_existing_workflow true and expand enhanced_question from the prior next-step action.
When the user asks to Run a quoted workflow name (especially with sample data), set intent=ask,
metadata.wants_sample_run=true, metadata.workflow_name from the quotes, and enhanced_question that
describes running that workflow with sample data (explain failures after the run if requested).

Disposition rules (thinking layer — same response):
- plan: new workflow on canvas OR numbered fix/extension plan before canvas changes.
- answer: run review, platform Q&A, sample run, load, automate, clear canvas edits — respond directly.
- clarify: ONLY unclear NEW builds when sources, outputs, or node types are genuinely unknown.
  Put questions in clarify_questions (0 when clear; scale count to vagueness, max 4).
- After run review, "show the plan" means a numbered FIX plan (disposition=plan, intent=ask) — not rebuild.
- thinking: engineer monologue; never echo "User asked:" verbatim; end with what you will do next."""

_FENCED_JSON = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)

_VALID_INTENTS = frozenset({
    "build", "ask", "automate", "load",
    "explain_run", "explain_error", "query_run_data",
})


@dataclass(frozen=True)
class SherpaRoute:
    intent: str
    reason: str
    enhanced_question: str
    keywords: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)
    source: str = "llm"

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "reason": self.reason,
            "enhanced_question": self.enhanced_question,
            "keywords": list(self.keywords),
            "metadata": dict(self.metadata),
            "source": self.source,
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
    match = _FENCED_JSON.search(raw)
    if match:
        try:
            parsed = json.loads(match.group(1))
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None
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


def _format_context(
    *,
    has_workflow: bool,
    workflow_name: str | None,
    has_run_log: bool,
    run_id: str | None,
    run_workflow_name: str | None,
    recent_errors: list[dict] | None,
    thread_context: str | None = None,
    recent_run_workflows: list[str] | None = None,
) -> str:
    lines: list[str] = []
    if thread_context:
        lines.append("- Recent conversation in this thread:")
        for line in thread_context.strip().splitlines()[:16]:
            lines.append(f"  {line}")
    if has_workflow:
        label = workflow_name or "unnamed"
        lines.append(f"- A workflow is loaded on the canvas: {label!r}")
    else:
        lines.append("- No workflow loaded on the canvas.")
    if has_run_log:
        rid = run_id or "unknown"
        rwf = run_workflow_name or workflow_name or "unknown"
        lines.append(f"- A completed run is in memory: run_id={rid!r}, workflow={rwf!r}")
    if recent_run_workflows:
        lines.append("- Recent run history workflow names:")
        for name in recent_run_workflows[:5]:
            lines.append(f"  · {name}")
    if recent_errors:
        lines.append(f"- {len(recent_errors)} recent validator/runtime error(s):")
        for err in recent_errors[:4]:
            if not isinstance(err, dict):
                continue
            msg = str(err.get("message") or err).strip()
            node_id = err.get("node_id")
            prefix = f"{node_id}: " if node_id else ""
            lines.append(f"  · {prefix}{msg[:160]}")
    return "\n".join(lines) if lines else "- No extra studio context."


def _normalize_metadata(raw: Any) -> dict[str, Any]:
    meta = raw if isinstance(raw, dict) else {}
    return {
        "workflow_name": meta.get("workflow_name") or None,
        "run_selector": meta.get("run_selector") or None,
        "run_id": meta.get("run_id") or None,
        "run_status_filter": meta.get("run_status_filter") or None,
        "error_message": meta.get("error_message") or None,
        "node_id": meta.get("node_id") or None,
        "topics": list(meta.get("topics") or []) if isinstance(meta.get("topics"), list) else [],
        "wants_sql": bool(meta.get("wants_sql")),
        "edit_existing_workflow": bool(meta.get("edit_existing_workflow")),
        "wants_sample_run": bool(meta.get("wants_sample_run")),
        "slash_route": meta.get("slash_route") or None,
        "suggested_sql": meta.get("suggested_sql") or None,
        "wants_outlook": bool(meta.get("wants_outlook")),
        "wants_validation": bool(meta.get("wants_validation")),
        "verification_plan": _normalize_verification_plan(meta.get("verification_plan")),
    }


def _normalize_verification_plan(raw: Any) -> list[str] | None:
    if not isinstance(raw, list):
        return None
    plan = [str(p).strip() for p in raw if str(p).strip()]
    return plan or None


def _parse_route(parsed: dict[str, Any], *, fallback_message: str, source: str) -> SherpaRoute:
    intent = str(parsed.get("intent") or "ask").strip().lower()
    if intent not in _VALID_INTENTS:
        intent = "ask"
    reason = str(parsed.get("reason") or "LLM routing").strip()[:240]
    enhanced = str(parsed.get("enhanced_question") or fallback_message).strip()
    if not enhanced:
        enhanced = fallback_message
    kw_raw = parsed.get("keywords")
    keywords: tuple[str, ...] = tuple(
        str(k).strip() for k in kw_raw if str(k).strip()
    ) if isinstance(kw_raw, list) else ()
    metadata = _normalize_metadata(parsed.get("metadata"))
    disposition = str(parsed.get("disposition") or "").strip().lower()
    if disposition in ("plan", "answer", "clarify"):
        metadata["router_disposition"] = disposition
        metadata["sherpa_disposition"] = disposition
    confidence = parsed.get("confidence")
    if confidence is not None:
        try:
            metadata["disposition_confidence"] = float(confidence)
        except (TypeError, ValueError):
            pass
    thinking = str(parsed.get("thinking") or "").strip()
    if thinking:
        metadata["thinking_preview"] = thinking
        metadata["router_thinking"] = thinking
    clarify_raw = parsed.get("clarify_questions")
    if isinstance(clarify_raw, list) and clarify_raw:
        metadata["router_clarify_questions"] = [q for q in clarify_raw if isinstance(q, dict)]
    return SherpaRoute(
        intent=intent,
        reason=reason,
        enhanced_question=enhanced,
        keywords=keywords,
        metadata=metadata,
        source=source,
    )


def _coalesce_run_output_intent(route: SherpaRoute, message: str) -> SherpaRoute:
    """Map natural-language run output questions from query_run_data to explain_run."""
    from copilot.run_output_questions import is_run_output_question

    if route.intent != "query_run_data":
        return route
    if not is_run_output_question(message):
        return route
    if re.search(r"\bselect\b", message, re.IGNORECASE):
        return route
    return SherpaRoute(
        intent="explain_run",
        reason=route.reason,
        enhanced_question=route.enhanced_question,
        keywords=route.keywords,
        metadata=route.metadata,
        source=route.source,
    )


def _clear_phantom_edit_metadata(
    meta: dict[str, Any],
    *,
    message: str = "",
    canvas_workflow: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Drop edit_existing when the named workflow is not on canvas or in the library."""
    if not meta.get("edit_existing_workflow"):
        return meta
    if (canvas_workflow or {}).get("nodes"):
        return meta
    wf_name = str(meta.get("workflow_name") or "").strip()
    if not wf_name:
        quoted = _NAMED_RUN_QUOTED_RE.search((message or "").strip())
        if quoted:
            wf_name = quoted.group(1).strip()
    if not wf_name:
        return meta
    try:
        from app.workflow_library import workflow_exists_in_catalog

        if workflow_exists_in_catalog(wf_name):
            return meta
    except Exception:
        return meta
    cleared = dict(meta)
    cleared["edit_existing_workflow"] = False
    return cleared


def finalize_sherpa_route(
    route: SherpaRoute,
    *,
    message: str,
    thread_context: str | None = None,
    canvas_workflow: dict[str, Any] | None = None,
) -> SherpaRoute:
    """Post-process router output for follow-ups and session metadata."""
    from copilot.follow_up import (
        _looks_like_delta_edit,
        action_follow_up_build_override,
        action_follow_up_create_build_override,
        action_follow_up_outlook_unavailable_override,
        action_follow_up_run_override,
        enrich_route_metadata_for_follow_up,
        repair_follow_up_text,
    )

    meta = enrich_route_metadata_for_follow_up(
        route.metadata,
        message=message,
        thread_context=thread_context,
        canvas_workflow=canvas_workflow,
    )
    meta = _clear_phantom_edit_metadata(meta, message=message, canvas_workflow=canvas_workflow)
    enhanced = route.enhanced_question or message
    if meta.get("edit_existing_workflow") or _looks_like_delta_edit((message or "").lower()):
        enhanced = repair_follow_up_text(
            enhanced,
            thread_context=thread_context,
            canvas_workflow=canvas_workflow,
        )
    out = SherpaRoute(
        intent=route.intent,
        reason=route.reason,
        enhanced_question=enhanced,
        keywords=route.keywords,
        metadata=meta,
        source=route.source,
    )
    out = _coalesce_run_output_intent(out, message)
    outlook_override = action_follow_up_outlook_unavailable_override(
        message,
        canvas_workflow=canvas_workflow,
    )
    if outlook_override:
        merged_meta = {**out.metadata, **outlook_override.get("metadata", {})}
        return SherpaRoute(
            intent=str(outlook_override["intent"]),
            reason=str(outlook_override.get("reason") or out.reason),
            enhanced_question=str(outlook_override.get("enhanced_question") or out.enhanced_question),
            keywords=out.keywords,
            metadata=merged_meta,
            source=str(outlook_override.get("source") or "follow_up_outlook"),
        )
    run_override = action_follow_up_run_override(
        message,
        thread_context=thread_context,
        canvas_workflow=canvas_workflow,
    )
    if run_override:
        merged_meta = {**out.metadata, **run_override.get("metadata", {})}
        return SherpaRoute(
            intent=str(run_override["intent"]),
            reason=str(run_override.get("reason") or out.reason),
            enhanced_question=str(run_override.get("enhanced_question") or out.enhanced_question),
            keywords=out.keywords,
            metadata=merged_meta,
            source=str(run_override.get("source") or "follow_up_run"),
        )
    from copilot.intent_layer import action_follow_up_show_fix_plan_override

    fix_plan_override = action_follow_up_show_fix_plan_override(
        message,
        thread_context=thread_context,
        canvas_workflow=canvas_workflow,
    )
    if fix_plan_override:
        merged_meta = {**out.metadata, **fix_plan_override.get("metadata", {})}
        return SherpaRoute(
            intent=str(fix_plan_override["intent"]),
            reason=str(fix_plan_override.get("reason") or out.reason),
            enhanced_question=str(fix_plan_override.get("enhanced_question") or out.enhanced_question),
            keywords=out.keywords,
            metadata=merged_meta,
            source=str(fix_plan_override.get("source") or "follow_up_show_fix_plan"),
        )

    create_override = action_follow_up_create_build_override(
        message,
        thread_context=thread_context,
        canvas_workflow=canvas_workflow,
    )
    if create_override:
        merged_meta = {**out.metadata, **create_override.get("metadata", {})}
        return SherpaRoute(
            intent=str(create_override["intent"]),
            reason=str(create_override.get("reason") or out.reason),
            enhanced_question=str(create_override.get("enhanced_question") or out.enhanced_question),
            keywords=out.keywords,
            metadata=merged_meta,
            source=str(create_override.get("source") or "follow_up_create"),
        )
    override = action_follow_up_build_override(
        message,
        thread_context=thread_context,
        canvas_workflow=canvas_workflow,
    )
    if override:
        merged_meta = {**out.metadata, **override.get("metadata", {})}
        return SherpaRoute(
            intent=str(override["intent"]),
            reason=str(override.get("reason") or out.reason),
            enhanced_question=str(override.get("enhanced_question") or out.enhanced_question),
            keywords=out.keywords,
            metadata=merged_meta,
            source=str(override.get("source") or "follow_up"),
        )
    return out


_NAMED_RUN_QUOTED_RE = re.compile(r'["\']([^"\']{3,120})["\']')


def _apply_named_run_route_override(route: SherpaRoute, message: str) -> SherpaRoute:
    """Run 'Workflow Name' with sample → load + execute, not workflow-not-found clarify."""
    text = (message or "").strip()
    lower = text.lower()
    if not re.search(r"\brun\b", lower):
        return route
    if not re.search(r"\bwith\s+sample\b|\bsample\s+(?:alert|data|run)\b", lower):
        return route
    quoted = _NAMED_RUN_QUOTED_RE.search(text)
    wf_name = (quoted.group(1).strip() if quoted else "") or str(
        (route.metadata or {}).get("workflow_name") or "",
    ).strip()
    meta = dict(route.metadata or {})
    if wf_name:
        meta["workflow_name"] = wf_name
    meta["wants_sample_run"] = True
    meta["edit_existing_workflow"] = False
    meta.pop("propose_build_plan", None)
    explain = bool(re.search(r"\b(explain|fail|error|broken)\b", lower))
    enhanced = route.enhanced_question or text
    if wf_name and explain:
        enhanced = (
            f"Run **{wf_name}** with sample data, then explain any failures or unexpected output."
        )
    elif wf_name:
        enhanced = f"Run **{wf_name}** with sample data."
    return SherpaRoute(
        intent="ask",
        reason="Named workflow run with sample data",
        enhanced_question=enhanced,
        keywords=route.keywords,
        metadata=meta,
        source="heuristic_named_run",
    )


_NAMED_EDIT_VERB_RE = re.compile(
    r"\b(improve|fix|wire|connect|extend|update)\b",
    re.IGNORECASE,
)


def _apply_named_edit_route_override(
    route: SherpaRoute,
    message: str,
    *,
    has_workflow: bool = False,
    canvas_workflow: dict[str, Any] | None = None,
) -> SherpaRoute:
    """Improve/fix a named workflow on canvas — execute edit, not plan-first."""
    text = (message or "").strip()
    lower = text.lower()
    if str(route.intent) in ("explain_run", "explain_error", "query_run_data", "load", "automate"):
        return route
    if re.search(
        r"\b(review|reliability|latest run|last run|run log|run summary|row count|how many rows)\b",
        lower,
    ):
        return route
    if re.search(r"\bsuggest\s+(one\s+)?change\b", lower):
        return route
    has_canvas = bool((canvas_workflow or {}).get("nodes"))
    if not has_workflow and not has_canvas:
        return route
    if not _NAMED_EDIT_VERB_RE.search(lower):
        return route
    quoted = _NAMED_RUN_QUOTED_RE.search(text)
    wf_name = (quoted.group(1).strip() if quoted else "") or str(
        (route.metadata or {}).get("workflow_name") or "",
    ).strip()
    canvas_name = str((canvas_workflow or {}).get("name") or "").strip()
    if not wf_name and not canvas_name:
        return route
    meta = dict(route.metadata or {})
    meta["edit_existing_workflow"] = True
    meta.pop("propose_build_plan", None)
    if wf_name:
        meta["workflow_name"] = wf_name
    elif canvas_name:
        meta["workflow_name"] = canvas_name
    target = wf_name or canvas_name
    enhanced = route.enhanced_question or text
    if target and target not in enhanced:
        enhanced = f"Apply to **{target}** on the canvas: {text}"
    return SherpaRoute(
        intent="build",
        reason="Named workflow edit on existing canvas workflow",
        enhanced_question=enhanced,
        keywords=route.keywords,
        metadata=meta,
        source="heuristic_named_edit",
    )


_LOAD_VERB_RE = re.compile(r"\b(load|open|pull up|switch to|find|show me)\b", re.IGNORECASE)


def _apply_named_load_route_override(route: SherpaRoute, message: str) -> SherpaRoute:
    """Load 'Workflow Name' or load … onto canvas — without requiring the word workflow."""
    text = (message or "").strip()
    lower = text.lower()
    if str(route.intent) == "load":
        meta = dict(route.metadata or {})
        quoted = _NAMED_RUN_QUOTED_RE.search(text)
        if quoted and not meta.get("workflow_name"):
            meta["workflow_name"] = quoted.group(1).strip()
        if meta != route.metadata:
            return SherpaRoute(
                intent=route.intent,
                reason=route.reason,
                enhanced_question=route.enhanced_question,
                keywords=route.keywords,
                metadata=meta,
                source=route.source,
            )
        return route
    if not _LOAD_VERB_RE.search(lower):
        return route
    if re.search(r"\b(create|build|make|generate|upload)\b", lower):
        return route
    quoted = _NAMED_RUN_QUOTED_RE.search(text)
    onto_canvas = bool(re.search(r"\bonto the canvas\b", lower))
    mentions_workflow = bool(re.search(r"\b(workflow|pipeline)\b", lower))
    if not quoted and not onto_canvas and not mentions_workflow:
        return route
    wf_name = (quoted.group(1).strip() if quoted else "") or str(
        (route.metadata or {}).get("workflow_name") or "",
    ).strip()
    meta = dict(route.metadata or {})
    if wf_name:
        meta["workflow_name"] = wf_name
    enhanced = route.enhanced_question or text
    if wf_name:
        enhanced = f'Load **{wf_name}** onto the canvas.'
    return SherpaRoute(
        intent="load",
        reason="Named workflow load onto canvas",
        enhanced_question=enhanced,
        keywords=route.keywords,
        metadata=meta,
        source="heuristic_named_load",
    )


def _apply_route_heuristic_overrides(
    route: SherpaRoute,
    message: str,
    *,
    has_workflow: bool = False,
    canvas_workflow: dict[str, Any] | None = None,
) -> SherpaRoute:
    from copilot.run_output_questions import is_run_output_question
    from generation.harness.intent import is_advisory_question_heuristic

    if is_run_output_question(message):
        if str(route.intent) == "ask":
            meta = dict(route.metadata or {})
            meta.setdefault("wants_sql", True)
            meta.setdefault("verification_plan", ["row_counts"])
            route = SherpaRoute(
                intent="explain_run",
                reason="Run output question — prefer explain_run over platform ask",
                enhanced_question=route.enhanced_question or message,
                keywords=route.keywords,
                metadata=meta,
                source=route.source or "heuristic_run_output",
            )
    elif is_advisory_question_heuristic(message):
        meta = dict(route.metadata or {})
        meta["router_disposition"] = "answer"
        meta["sherpa_disposition"] = "answer"
        meta.pop("router_clarify_questions", None)
        return SherpaRoute(
            intent="ask",
            reason=route.reason or "Platform Q&A",
            enhanced_question=route.enhanced_question or message,
            keywords=route.keywords,
            metadata=meta,
            source=route.source,
        )
    route = _apply_named_run_route_override(route, message)
    route = _apply_named_load_route_override(route, message)
    return _apply_named_edit_route_override(
        route,
        message,
        has_workflow=has_workflow,
        canvas_workflow=canvas_workflow,
    )


def route_sherpa_message(
    message: str,
    *,
    has_workflow: bool = False,
    workflow_name: str | None = None,
    has_run_log: bool = False,
    run_id: str | None = None,
    run_workflow_name: str | None = None,
    recent_errors: list[dict] | None = None,
    thread_context: str | None = None,
    recent_run_workflows: list[str] | None = None,
    adapter: GeminiAdapter | None = None,
    canvas_workflow: dict[str, Any] | None = None,
) -> SherpaRoute:
    """Classify user message into structured SherpaRoute for downstream handlers."""
    text = (message or "").strip()
    if not text:
        return SherpaRoute(
            intent="ask",
            reason="Empty message",
            enhanced_question="",
            source="heuristic",
        )

    from copilot.sherpa_routes import route_message_with_slash

    forced = route_message_with_slash(text, canvas_workflow=canvas_workflow)
    if forced is not None:
        return finalize_sherpa_route(
            forced,
            message=text,
            thread_context=thread_context,
            canvas_workflow=canvas_workflow,
        )

    if not gemini_configured():
        route = _heuristic_route(
            text,
            has_workflow=has_workflow,
            has_run_log=has_run_log,
            canvas_workflow=canvas_workflow,
        )
        route = _apply_route_heuristic_overrides(
            route,
            text,
            has_workflow=has_workflow,
            canvas_workflow=canvas_workflow,
        )
        return finalize_sherpa_route(
            route,
            message=text,
            thread_context=thread_context,
            canvas_workflow=canvas_workflow,
        )

    context = _format_context(
        has_workflow=has_workflow,
        workflow_name=workflow_name,
        has_run_log=has_run_log,
        run_id=run_id,
        run_workflow_name=run_workflow_name,
        recent_errors=recent_errors,
        thread_context=thread_context,
        recent_run_workflows=recent_run_workflows,
    )
    user_turn = f"User message:\n{text}\n\nStudio context:\n{context}"
    raw = (adapter or get_default_adapter()).chat_turn(
        system_prompt=_ROUTE_SYSTEM,
        history=[],
        user_turn=user_turn,
        temperature=0.0,
        json_mode=True,
    )
    parsed = _extract_json(raw) or {}
    route = _parse_route(parsed, fallback_message=text, source="llm")
    route = _apply_route_heuristic_overrides(
        route,
        text,
        has_workflow=has_workflow,
        canvas_workflow=canvas_workflow,
    )
    return finalize_sherpa_route(
        route,
        message=text,
        thread_context=thread_context,
        canvas_workflow=canvas_workflow,
    )


def _heuristic_route(
    text: str,
    *,
    has_workflow: bool,
    has_run_log: bool,
    canvas_workflow: dict[str, Any] | None = None,
) -> SherpaRoute:
    """Minimal fallback when Gemini is unavailable (tests only)."""
    from copilot.sherpa_routes import route_message_with_slash

    forced = route_message_with_slash(text, canvas_workflow=canvas_workflow)
    if forced is not None:
        return forced

    from copilot.run_output_questions import is_run_output_question
    from generation.harness.intent import is_advisory_question_heuristic

    lower = text.lower()
    if is_run_output_question(text) or "reliability" in lower or "latest run" in lower:
        return SherpaRoute(
            intent="explain_run",
            reason="Run output question heuristic",
            enhanced_question=text,
            keywords=tuple(),
            metadata={
                "run_selector": "current" if has_run_log else "latest",
                "wants_sql": True,
                "verification_plan": ["row_counts", "join_orphans"],
            },
            source="heuristic",
        )
    if _looks_like_error_question(lower):
        return SherpaRoute(
            intent="explain_error",
            reason="Error question heuristic",
            enhanced_question=text,
            source="heuristic",
        )
    if "select " in lower and "from" in lower:
        return SherpaRoute(
            intent="query_run_data",
            reason="SQL-like question heuristic",
            enhanced_question=text,
            metadata={"wants_sql": True},
            source="heuristic",
        )
    if is_advisory_question_heuristic(text):
        return SherpaRoute(intent="ask", reason="Advisory question heuristic", enhanced_question=text, source="heuristic")
    import re
    load_re = re.compile(
        r"\b(load|open|find|pull up|switch to|show me)\b"
        r'(?:.{0,48}\b(workflow|pipeline)\b|.{0,28}(?:"[^"]{3,120}"|\'[^\']{3,120}\')|.{0,36}\bonto the canvas\b)',
        re.IGNORECASE,
    )
    auto_re = re.compile(
        r"\b(automation|automate|scheduled|schedule this|run at|run every|daily at|cron)\b",
        re.IGNORECASE,
    )
    if load_re.search(text):
        return SherpaRoute(intent="load", reason="Load workflow heuristic", enhanced_question=text, source="heuristic")
    if auto_re.search(text):
        return SherpaRoute(intent="automate", reason="Automation heuristic", enhanced_question=text, source="heuristic")
    del has_workflow
    return SherpaRoute(
        intent="build",
        reason="Heuristic fallback",
        enhanced_question=text,
        source="heuristic",
    )


def _looks_like_error_question(lower: str) -> bool:
    """Avoid routing 'branch for failures' improve requests to explain_error."""
    if re.search(r"\b(improve|validation|branch|outlook|add|extend|enhance)\b", lower):
        return False
    return bool(
        re.search(r"\bfail(?:ure|ures|ed)?\b", lower)
        or re.search(r"\berror\b", lower)
    )
