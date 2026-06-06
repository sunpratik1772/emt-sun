"""Sherpa intent ambiguity layer — confirm or clarify before executing routed actions."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from copilot.follow_up import looks_like_action_acceptance
from copilot.next_action import (
    is_sample_run_next_step,
    last_next_step_from_thread,
    parse_next_action_from_text,
)
from llm import GeminiAdapter, gemini_configured, get_default_adapter

_BUILD_CLARIFY_SYSTEM = """You generate clarifying questions ONLY for unclear NEW workflow builds (or major extensions).

Return JSON only:
{
  "needs_clarification": true|false,
  "questions": [
    {
      "id": "q1",
      "kind": "confirm"|"choice",
      "allow_multiple": false,
      "question": "question text",
      "options": [
        {"id": "a", "label": "Short label", "description": "helper under 120 chars"}
      ],
      "default_option_id": "a"|null
    }
  ],
  "reason": "one sentence"
}

Rules (grill-me style — challenge vague language against node catalog + data schema):
- needs_clarification=false when message + thread + schema give enough to plan or build.
- Ask 0 questions (needs_clarification=false) when the user already named sources, transforms, and outputs.
- Scale count to uncertainty: very vague → up to 4; partially clear → 1-2; detailed → 0.
- Challenge overloaded terms: "account", "report", "alert" — offer precise options tied to node types.
- When data source is unknown, ask which file/table/integration (options from schema hints when present).
- When output format is unknown, ask csv/excel/email/agent response.
- kind=confirm for yes/no; kind=choice for exclusive or multi-select options.
- Do NOT include id=other — UI adds "Something else" last.
- NEVER ask for: run reviews, sample runs, load, automate, explain_error, platform Q&A, plan-only phases.
- Never ask when propose_build_plan=true or propose_fix_plan=true (plan streams first).
- Keep questions under 220 chars; option descriptions under 120 chars."""


@dataclass(frozen=True)
class ClarificationOption:
    id: str
    label: str
    description: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "label": self.label, "description": self.description}


OTHER_OPTION_ID = "other"
OTHER_OPTION_LABEL = "Something else"
OTHER_OPTION_DESCRIPTION = "Describe what you want in your own words"


@dataclass
class ClarificationQuestion:
    id: str
    kind: str  # confirm | choice
    question: str
    options: list[ClarificationOption] = field(default_factory=list)
    default_option_id: str | None = None
    allow_multiple: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "question": self.question,
            "options": [o.to_dict() for o in self.options],
            "default_option_id": self.default_option_id,
            "allow_multiple": self.allow_multiple,
        }


@dataclass
class SherpaClarification:
    needed: bool
    questions: list[ClarificationQuestion] = field(default_factory=list)
    reason: str = ""

    @property
    def kind(self) -> str:
        return self.questions[0].kind if self.questions else ""

    @property
    def question(self) -> str:
        return self.questions[0].question if self.questions else ""

    @property
    def options(self) -> list[ClarificationOption]:
        return self.questions[0].options if self.questions else []

    @property
    def default_option_id(self) -> str | None:
        return self.questions[0].default_option_id if self.questions else None

    def to_dict(self) -> dict[str, Any]:
        qs = [q.to_dict() for q in self.questions] if self.needed else []
        first = self.questions[0] if self.questions else None
        return {
            "needed": self.needed,
            "questions": qs,
            "kind": first.kind if first else None,
            "question": first.question if first else "",
            "options": [o.to_dict() for o in first.options] if first else [],
            "default_option_id": first.default_option_id if first else None,
            "reason": self.reason,
        }


def _confirm_options() -> list[ClarificationOption]:
    return [
        ClarificationOption("yes", "Yes", "Proceed with this action"),
        ClarificationOption("no", "No", "Cancel — do not run or change anything yet"),
        ClarificationOption(OTHER_OPTION_ID, OTHER_OPTION_LABEL, OTHER_OPTION_DESCRIPTION),
    ]


def normalize_clarification_options(
    options: list[ClarificationOption],
    *,
    kind: str,
) -> list[ClarificationOption]:
    """Ensure the last option is always Something else (no duplicate other)."""
    if kind == "confirm":
        return _confirm_options()
    cleaned: list[ClarificationOption] = []
    for opt in options:
        oid = (opt.id or "").strip().lower()
        label_lower = (opt.label or "").lower()
        if oid == OTHER_OPTION_ID or "something else" in label_lower or label_lower == "other…":
            continue
        cleaned.append(opt)
    cleaned.append(
        ClarificationOption(OTHER_OPTION_ID, OTHER_OPTION_LABEL, OTHER_OPTION_DESCRIPTION),
    )
    return cleaned


_RUN_NAMED_WORKFLOW_RE = re.compile(
    r'\brun\s+["\']|["\'][^"\']{3,120}["\'].*\bwith\s+sample\b|\bwith\s+sample\b.*["\'][^"\']{3,120}["\']',
    re.IGNORECASE,
)


def _message_requests_named_run(message: str) -> bool:
    """True when the user asks to execute a named workflow (often with sample data)."""
    text = (message or "").strip()
    if not text:
        return False
    return bool(_RUN_NAMED_WORKFLOW_RE.search(text))


def _workflow_exists_in_library(workflow_name: str) -> bool:
    """Check canonical catalog before claiming a workflow is missing."""
    from app.request_context import get_current_user_id
    from app.workflow_library import workflow_exists_in_catalog

    return workflow_exists_in_catalog(workflow_name, get_current_user_id())


def _workflow_not_found_questions(workflow_name: str) -> list[ClarificationQuestion]:
    name = (workflow_name or "that workflow").strip()
    return [
        ClarificationQuestion(
            id="q_workflow_missing",
            kind="choice",
            question=f"The workflow '{name}' was not found. What would you like to do?",
            options=normalize_clarification_options(
                [
                    ClarificationOption(
                        "a",
                        "List existing workflows",
                        "Show saved and draft workflows from the library",
                    ),
                    ClarificationOption(
                        "b",
                        "Create a new workflow",
                        f"Start building a new workflow named '{name}'",
                    ),
                    ClarificationOption(
                        "c",
                        "Provide a different workflow name",
                        "Enter the correct name for the workflow you want",
                    ),
                ],
                kind="choice",
            ),
            default_option_id="b",
            allow_multiple=True,
        ),
    ]


def _parse_clarification_questions(parsed: dict[str, Any]) -> list[ClarificationQuestion]:
    """Parse LLM or legacy single-question clarification JSON."""
    raw_questions = parsed.get("questions")
    if isinstance(raw_questions, list) and raw_questions:
        out: list[ClarificationQuestion] = []
        for i, item in enumerate(raw_questions[:3]):
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind") or "choice").strip().lower()
            if kind not in ("confirm", "choice"):
                kind = "choice"
            options: list[ClarificationOption] = []
            for opt in item.get("options") or []:
                if not isinstance(opt, dict):
                    continue
                oid = str(opt.get("id") or "").strip().lower()
                if not oid:
                    continue
                options.append(
                    ClarificationOption(
                        id=oid,
                        label=str(opt.get("label") or oid),
                        description=str(opt.get("description") or ""),
                    )
                )
            if kind == "confirm" and not options:
                options = _confirm_options()
            elif not options:
                continue
            allow_multiple = bool(item.get("allow_multiple"))
            if kind == "confirm":
                allow_multiple = False
            elif "allow_multiple" not in item:
                allow_multiple = True
            qtext = str(item.get("question") or "").strip()
            if not qtext:
                continue
            out.append(
                ClarificationQuestion(
                    id=str(item.get("id") or f"q{i + 1}"),
                    kind=kind,
                    question=qtext,
                    options=normalize_clarification_options(options, kind=kind),
                    default_option_id=str(item.get("default_option_id") or "").strip() or None,
                    allow_multiple=allow_multiple,
                ),
            )
        return out

    kind = str(parsed.get("kind") or "confirm").strip().lower()
    if kind not in ("confirm", "choice"):
        kind = "choice"
    options: list[ClarificationOption] = []
    for item in parsed.get("options") or []:
        if not isinstance(item, dict):
            continue
        oid = str(item.get("id") or "").strip().lower()
        if not oid:
            continue
        options.append(
            ClarificationOption(
                id=oid,
                label=str(item.get("label") or oid),
                description=str(item.get("description") or ""),
            )
        )
    if not options:
        options = _confirm_options()
    qtext = str(parsed.get("question") or "What should I do next?").strip()
    return [
        ClarificationQuestion(
            id="q1",
            kind=kind,
            question=qtext,
            options=normalize_clarification_options(options, kind=kind),
            default_option_id=str(parsed.get("default_option_id") or "").strip() or None,
            allow_multiple=kind == "choice",
        ),
    ]


def _sample_run_confirm_question(workflow_name: str | None) -> str:
    name = (workflow_name or "the workflow on the canvas").strip()
    return f"Just to confirm — should I execute a sample run of **{name}** now?"


def _heuristic_assess(
    route: Any,
    message: str,
    *,
    thread_context: str | None,
    has_workflow: bool,
    canvas_workflow: dict[str, Any] | None,
) -> SherpaClarification | None:
    """Fast path: return clarification payload or None to defer to LLM / proceed."""
    text = (message or "").strip()
    lower = text.lower()
    meta = dict(getattr(route, "metadata", None) or {})
    source = str(getattr(route, "source", "") or "")

    if meta.get("clarification_resolved") or source.startswith("clarification_"):
        return None

    if meta.get("slash_route"):
        return None

    if meta.get("propose_build_plan"):
        return SherpaClarification(
            needed=False,
            reason="Build plan phase streams the plan first; approval follows in the Questions panel.",
        )

    # Sample-run and named run requests execute directly — no workflow-not-found gate.
    if meta.get("wants_sample_run") or _message_requests_named_run(text):
        return SherpaClarification(
            needed=False,
            reason="Run request proceeds without workflow-not-found confirmation.",
        )

    if looks_like_action_acceptance(text):
        action, question = last_next_step_from_thread(thread_context or "")
        if is_sample_run_next_step(action, question):
            return None
        if not action and not question:
            return SherpaClarification(
                needed=True,
                questions=[
                    ClarificationQuestion(
                        id="q_confirm_step",
                        kind="confirm",
                        question=(
                            "I am not sure which step you want me to take. "
                            "Should I apply the last change Sherpa suggested on the canvas?"
                        ),
                        options=_confirm_options(),
                        default_option_id="yes",
                        allow_multiple=False,
                    ),
                ],
                reason="Short affirmation without a clear prior next-step in thread context.",
            )

    intent = str(getattr(route, "intent", "") or "")
    wf_name = str(meta.get("workflow_name") or "").strip()
    if not wf_name:
        quoted = re.search(r"['\"]([^'\"]{3,120})['\"]", text)
        if quoted:
            wf_name = quoted.group(1).strip()

    if (
        intent in ("explain_run", "explain_error", "load", "ask", "build")
        and not has_workflow
        and not (canvas_workflow or {}).get("nodes")
        and wf_name
    ):
        if meta.get("propose_build_plan") or meta.get("awaiting_plan_revision"):
            return None
        if _message_requests_named_run(text):
            return None
        if intent in ("ask", "build") and not meta.get("edit_existing_workflow"):
            return None
        if str(source or "").startswith(
            ("build_plan_gate", "clarification_create_plan", "clarification_plan_rejected")
        ):
            return None
        if _workflow_exists_in_library(wf_name):
            return None
        return SherpaClarification(
            needed=True,
            questions=_workflow_not_found_questions(wf_name),
            reason="Named workflow is not on the canvas or in the library.",
        )

    if intent in ("explain_run", "explain_error") and (
        has_workflow or bool((canvas_workflow or {}).get("nodes"))
    ):
        return SherpaClarification(
            needed=False,
            reason="Run review with canvas workflow and/or run log is unambiguous.",
        )

    if intent == "load" and not has_workflow:
        load_name = str(meta.get("workflow_name") or "").strip()
        if not load_name:
            quoted = re.search(r'["\']([^"\']{3,120})["\']', text)
            if quoted:
                load_name = quoted.group(1).strip()
        if load_name and _workflow_exists_in_library(load_name):
            return SherpaClarification(
                needed=False,
                reason="Explicit load of a library workflow — proceed without confirm.",
            )
        load_label = load_name or text
        return SherpaClarification(
            needed=True,
            questions=[
                ClarificationQuestion(
                    id="q_load_confirm",
                    kind="confirm",
                    question=f"Should I load **{load_label or 'that workflow'}** onto the canvas?",
                    options=_confirm_options(),
                    default_option_id="yes",
                    allow_multiple=False,
                ),
            ],
            reason="Load intent should be confirmed before replacing the canvas.",
        )

    if intent == "query_run_data" and re.search(r"\bsql\b", lower):
        return SherpaClarification(
            needed=True,
            questions=[
                ClarificationQuestion(
                    id="q_sql_layer",
                    kind="choice",
                    question="When you say SQL against runs, which layer should I use first?",
                    options=normalize_clarification_options(
                        [
                            ClarificationOption(
                                "a",
                                "Run history metadata",
                                "Query run_logs (workflow, status, dates, errors)",
                            ),
                            ClarificationOption(
                                "b",
                                "Output row data",
                                "SQL on a specific run's exported node output",
                            ),
                            ClarificationOption(
                                "c",
                                "Both",
                                "Filter runs by metadata, then query that run's output",
                            ),
                        ],
                        kind="choice",
                    ),
                    default_option_id="c",
                    allow_multiple=True,
                ),
            ],
            reason="SQL-like run questions often need a layer choice.",
        )

    if len(text) > 80 and intent == "build" and not looks_like_action_acceptance(text):
        return None

    return None


def _workflow_name_from_thread(thread_context: str, canvas_workflow: dict[str, Any] | None) -> str | None:
    from copilot.follow_up import _workflow_name_from_thread

    return _workflow_name_from_thread(thread_context, canvas_workflow)


_BUILD_SELECTION = re.compile(
    r"\b(create|build|make|generate|draft|new pipeline|new workflow|from scratch)\b",
    re.IGNORECASE,
)
_LOAD_SELECTION = re.compile(
    r"\b(load|open|find|existing|saved workflow|pull up)\b",
    re.IGNORECASE,
)


def _selection_blob(
    selection_id: str,
    selection_label: str | None,
    selection_description: str | None,
    other_text: str | None,
) -> str:
    return " ".join(
        p
        for p in (
            selection_id,
            selection_label or "",
            selection_description or "",
            other_text or "",
        )
        if p
    )


def _selection_implies_build(
    selection_id: str,
    selection_label: str | None = None,
    selection_description: str | None = None,
    other_text: str | None = None,
) -> bool:
    return bool(_BUILD_SELECTION.search(_selection_blob(selection_id, selection_label, selection_description, other_text)))


def _selection_implies_load(
    selection_id: str,
    selection_label: str | None = None,
    selection_description: str | None = None,
    other_text: str | None = None,
) -> bool:
    return bool(_LOAD_SELECTION.search(_selection_blob(selection_id, selection_label, selection_description, other_text)))


PLAN_APPROVAL_QUESTION_ID = "q_plan_approve"

_PLAN_APPROVAL_APPROVE_IDS = frozenset({"a", "yes", "approve"})
_PLAN_APPROVAL_REJECT_IDS = frozenset({"b", "no", "reject"})


def _is_plan_approval_entry(entry: dict[str, Any], meta: dict[str, Any] | None = None) -> bool:
    """True when a Questions-panel answer is approving/rejecting a presented build plan."""
    qid = str(entry.get("question_id") or entry.get("id") or "").strip()
    question_lower = (entry.get("question") or "").lower()
    kind = str(entry.get("kind") or "").strip().lower()
    if qid == PLAN_APPROVAL_QUESTION_ID:
        return True
    if "does this plan look good" in question_lower:
        return True
    if "approve this plan" in question_lower:
        return True
    if kind == "plan_approval":
        return True
    labels = [str(l).strip().lower() for l in (entry.get("selection_labels") or []) if str(l).strip()]
    selection_ids = [str(s).strip().lower() for s in (entry.get("selection_ids") or []) if s]
    if (meta or {}).get("propose_build_plan") and selection_ids:
        if selection_ids[0] in _PLAN_APPROVAL_APPROVE_IDS and any("approve" in l for l in labels):
            return True
        if selection_ids[0] in _PLAN_APPROVAL_REJECT_IDS and any("reject" in l for l in labels):
            return True
    return False


def _plan_approval_is_approve(entry: dict[str, Any]) -> bool:
    labels = [str(l).strip().lower() for l in (entry.get("selection_labels") or []) if str(l).strip()]
    for sel in (entry.get("selection_ids") or []):
        sid = str(sel).strip().lower()
        if sid in _PLAN_APPROVAL_APPROVE_IDS:
            return True
        if sid == "yes" or (labels and "approve" in labels[0]):
            return True
    return False


def _plan_approval_is_reject(entry: dict[str, Any]) -> bool:
    labels = [str(l).strip().lower() for l in (entry.get("selection_labels") or []) if str(l).strip()]
    for sel in (entry.get("selection_ids") or []):
        sid = str(sel).strip().lower()
        if sid in _PLAN_APPROVAL_REJECT_IDS:
            return True
        if sid == "no" or (labels and "reject" in labels[0]):
            return True
    return False


def build_plan_approval_clarification(
    *,
    workflow_name: str | None = None,
) -> SherpaClarification:
    """Questions-panel approval after a plan has been shown in chat."""
    name = (workflow_name or "the workflow").strip()
    return SherpaClarification(
        needed=True,
        questions=[
            ClarificationQuestion(
                id=PLAN_APPROVAL_QUESTION_ID,
                kind="confirm",
                question=f"Does this plan look good? Should I create **{name}** on the canvas?",
                options=[
                    ClarificationOption("yes", "Approve", "Create the workflow on the canvas from this plan"),
                    ClarificationOption("no", "Reject", "Do not build yet — revise or try a different approach"),
                ],
                default_option_id="yes",
                allow_multiple=False,
            ),
        ],
        reason="Plan was presented — confirm before harness build.",
    )


def _thread_user_messages(thread_context: str | None) -> list[str]:
    out: list[str] = []
    for line in (thread_context or "").splitlines():
        if line.startswith("User:"):
            text = line.removeprefix("User:").strip()
            if text and (not out or out[-1] != text):
                out.append(text)
    return out


def _route_plan_confirmed_build(
    route: dict[str, Any],
    meta: dict[str, Any],
    *,
    message: str,
    clarification_question: str | None = None,
    thread_context: str | None = None,
) -> dict[str, Any]:
    """User approved a presented build plan — run harness build on the canvas."""
    meta = dict(meta)
    meta["build_plan_confirmed"] = True
    meta["propose_build_plan"] = False
    meta["awaiting_plan_revision"] = False
    meta["edit_existing_workflow"] = False
    meta["wants_sample_run"] = False
    meta["clarification_resolved"] = True
    user_turns = _thread_user_messages(thread_context)
    original = (meta.get("original_user_request") or message or "").strip()
    if user_turns:
        build_prompt = "\n\n".join(user_turns)
        meta["original_user_request"] = build_prompt
    else:
        build_prompt = original
        meta["original_user_request"] = original
    if clarification_question:
        meta["clarification_question"] = clarification_question.strip()
    meta["clarification_answer"] = "Approve — create on canvas"
    route["intent"] = "build"
    route["reason"] = "User approved the build plan"
    route["enhanced_question"] = build_prompt
    route["metadata"] = meta
    route["source"] = "clarification_confirmed_build"
    return route


def _route_plan_revision(
    route: dict[str, Any],
    meta: dict[str, Any],
    *,
    message: str,
    revision_reason: str | None = None,
) -> dict[str, Any]:
    """User rejected the plan — revise with optional reason, then re-confirm."""
    from copilot.build_plan_gate import build_plan_ask_prompt

    meta = dict(meta)
    reason = (revision_reason or "").strip()
    meta["propose_build_plan"] = True
    meta["build_plan_confirmed"] = False
    meta["awaiting_plan_revision"] = True
    meta["wants_sample_run"] = False
    meta["edit_existing_workflow"] = False
    meta["clarification_resolved"] = True
    if reason:
        meta["plan_revision_reason"] = reason
        meta["clarification_answer"] = reason
    original = (meta.get("original_user_request") or message or "").strip()
    meta["original_user_request"] = original
    wf_name = str(meta.get("workflow_name") or "").strip() or None
    clar = reason or "User rejected the plan — ask what to change before rebuilding."
    route["intent"] = "ask"
    route["reason"] = "User rejected the build plan — revise before creating on canvas"
    route["enhanced_question"] = build_plan_ask_prompt(
        original,
        workflow_name=wf_name,
        clarification=clar,
    )
    route["metadata"] = meta
    route["source"] = "clarification_plan_rejected"
    return route


def _route_create_to_plan_phase(
    route: dict[str, Any],
    meta: dict[str, Any],
    *,
    message: str,
    answer: str,
    clarification_question: str | None = None,
) -> dict[str, Any]:
    """User chose create — show plan and confirm before harness build."""
    from copilot.build_plan_gate import build_plan_ask_prompt

    meta = dict(meta)
    meta["edit_existing_workflow"] = False
    meta["propose_build_plan"] = True
    meta["build_plan_confirmed"] = False
    meta["wants_sample_run"] = False
    meta["clarification_resolved"] = True
    meta["original_user_request"] = (meta.get("original_user_request") or message or "").strip()
    if answer.strip():
        meta["clarification_answer"] = answer.strip()
    if clarification_question:
        meta["clarification_question"] = clarification_question.strip()
    wf_name = str(meta.get("workflow_name") or "").strip() or None
    route["intent"] = "ask"
    route["reason"] = "User chose to create — present plan before building on canvas"
    route["enhanced_question"] = build_plan_ask_prompt(
        meta["original_user_request"],
        workflow_name=wf_name,
        clarification=answer,
    )
    route["metadata"] = meta
    route["source"] = "clarification_create_plan"
    return route


def _extract_json(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
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
        if raw[i] == "{":
            depth += 1
        elif raw[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    parsed = json.loads(raw[start : i + 1])
                    return parsed if isinstance(parsed, dict) else None
                except Exception:
                    return None
    return None


def _clarification_from_intent_layer(meta: dict[str, Any]) -> SherpaClarification | None:
    """Questions pre-generated by the unified intent layer."""
    if not meta.get("intent_layer_clarify"):
        return None
    raw_questions = meta.get("intent_layer_questions") or []
    if not isinstance(raw_questions, list) or not raw_questions:
        return SherpaClarification(needed=False, reason="Intent layer flagged clarify but produced no questions.")
    questions = _parse_clarification_questions({"questions": raw_questions})
    if not questions:
        return SherpaClarification(needed=False, reason="Intent layer questions were invalid.")
    return SherpaClarification(
        needed=True,
        questions=questions,
        reason=str(meta.get("intent_layer_clarify_reason") or "Intent layer needs more detail before planning."),
    )


def assess_route_clarification(
    route: Any,
    message: str,
    *,
    thread_context: str | None = None,
    has_workflow: bool = False,
    canvas_workflow: dict[str, Any] | None = None,
    adapter: GeminiAdapter | None = None,
) -> SherpaClarification:
    """Always invoked; returns needed=False when the agent may proceed without asking."""
    meta = dict(getattr(route, "metadata", None) or {})
    if not meta.get("clarification_resolved"):
        from generation.harness.intent import is_advisory_question_heuristic

        if is_advisory_question_heuristic(message):
            return SherpaClarification(
                needed=False,
                reason="Platform how-to / advisory question — answer directly.",
            )
    layer_clar = _clarification_from_intent_layer(meta)
    if layer_clar is not None:
        return layer_clar

    heuristic = _heuristic_assess(
        route,
        message,
        thread_context=thread_context,
        has_workflow=has_workflow,
        canvas_workflow=canvas_workflow,
    )
    if heuristic is not None:
        return heuristic

    if meta.get("wants_sample_run"):
        return SherpaClarification(
            needed=False,
            reason="Sample-run acceptance proceeds without extra confirmation.",
        )

    intent = str(getattr(route, "intent", "") or "")
    disposition = str(meta.get("sherpa_disposition") or "").strip().lower()

    # Clarify gate applies only to unclear build/plan paths — not run review, load, or Q&A.
    if disposition and disposition != "clarify":
        return SherpaClarification(
            needed=False,
            reason=f"Intent layer disposition is {disposition}; no clarify gate.",
        )
    if intent != "build" or meta.get("propose_build_plan") or meta.get("propose_fix_plan"):
        if intent == "build" and len((message or "").strip()) > 80:
            return SherpaClarification(
                needed=False,
                reason="Detailed build request proceeds without clarify.",
            )
        if intent != "build":
            return SherpaClarification(
                needed=False,
                reason="Clarify gate applies only to unclear new workflow builds.",
            )

    if meta.get("propose_build_plan") or meta.get("propose_fix_plan"):
        return SherpaClarification(
            needed=False,
            reason="Plan phase streams first; approval follows in the Questions panel.",
        )

    wf_name = str(meta.get("workflow_name") or "").strip()
    if not wf_name:
        quoted = re.search(r"['\"]([^'\"]{3,120})['\"]", message or "")
        if quoted:
            wf_name = quoted.group(1).strip()
    if (
        wf_name
        and not has_workflow
        and not (canvas_workflow or {}).get("nodes")
        and _workflow_exists_in_library(wf_name)
    ):
        return SherpaClarification(
            needed=False,
            reason="Named workflow exists in saved/draft library.",
        )

    if looks_like_action_acceptance(message):
        action, question = last_next_step_from_thread(thread_context or "")
        if is_sample_run_next_step(action, question):
            return SherpaClarification(
                needed=False,
                reason="Affirmative to sample-run offer proceeds like /run.",
            )

    if not gemini_configured() and adapter is None:
        return SherpaClarification(needed=False, reason="Gemini unavailable")

    intent = str(getattr(route, "intent", "") or "")
    meta = dict(getattr(route, "metadata", None) or {})
    from copilot.intent_layer import _canvas_datasets, _node_catalog_context

    user_turn = (
        f"User message:\n{message}\n\n"
        f"Proposed route:\nintent={intent}\nreason={getattr(route, 'reason', '')}\n"
        f"enhanced_question={getattr(route, 'enhanced_question', '')}\n"
        f"metadata={json.dumps(meta, default=str)[:1200]}\n\n"
        f"Studio: has_workflow={has_workflow}\n"
        f"canvas_datasets={_canvas_datasets(canvas_workflow)}\n"
        f"node_catalog={_node_catalog_context(canvas_workflow)}\n"
        f"Thread:\n{(thread_context or '')[-2500:]}"
    )
    try:
        raw = (adapter or get_default_adapter()).chat_turn(
            system_prompt=_BUILD_CLARIFY_SYSTEM,
            history=[],
            user_turn=user_turn,
            temperature=0.0,
            json_mode=True,
        )
        parsed = _extract_json(raw) or {}
    except Exception:
        return SherpaClarification(needed=False, reason="Clarification LLM failed")

    if not parsed.get("needs_clarification"):
        return SherpaClarification(
            needed=False,
            reason=str(parsed.get("reason") or "Intent is clear"),
        )

    questions = _parse_clarification_questions(parsed)
    if not questions:
        return SherpaClarification(needed=False, reason="Clarification had no valid questions")

    return SherpaClarification(
        needed=True,
        questions=questions,
        reason=str(parsed.get("reason") or "LLM flagged ambiguous intent"),
    )


_LIST_SELECTION = re.compile(
    r"\b(list|show|see|browse).{0,24}\b(workflow|saved|draft|library)\b",
    re.IGNORECASE,
)


def _selection_implies_list(
    selection_id: str,
    selection_label: str | None = None,
    selection_description: str | None = None,
    other_text: str | None = None,
) -> bool:
    return bool(
        _LIST_SELECTION.search(
            _selection_blob(selection_id, selection_label, selection_description, other_text),
        )
    )


def _format_answer_entry(answer: dict[str, Any]) -> str:
    other = (answer.get("other_text") or "").strip()
    labels = answer.get("selection_labels") or []
    if other and OTHER_OPTION_ID in (answer.get("selection_ids") or []):
        return other
    parts = [str(l).strip() for l in labels if str(l).strip()]
    return "; ".join(parts) if parts else other


def resolve_clarification_answers(
    *,
    answers: list[dict[str, Any]],
    pending_route: dict[str, Any],
    message: str,
    thread_context: str | None = None,
    has_workflow: bool = False,
    canvas_workflow: dict[str, Any] | None = None,
    adapter: GeminiAdapter | None = None,
) -> dict[str, Any]:
    """Apply one or more Questions-panel answers and return the executable route."""
    route = dict(pending_route or {})
    meta = dict(route.get("metadata") or {})
    pending_intent = str(route.get("intent") or "").strip().lower()
    recorded: list[dict[str, Any]] = []

    for item in answers:
        entry = {
            "question_id": str(item.get("question_id") or "").strip(),
            "question": str(item.get("question") or "").strip(),
            "kind": str(item.get("kind") or "choice"),
            "selection_ids": [str(s).strip().lower() for s in (item.get("selection_ids") or []) if s],
            "other_text": (item.get("other_text") or "").strip() or None,
            "selection_labels": list(item.get("selection_labels") or []),
        }
        recorded.append(entry)

    meta["clarification_answers"] = recorded
    meta["clarification_resolved"] = True
    route["metadata"] = meta

    eq = str(route.get("enhanced_question") or message).strip()
    for entry in recorded:
        line = _format_answer_entry(entry)
        if line:
            eq += f"\n\nQ: {entry['question']}\nA: {line}"
    route["enhanced_question"] = eq

    # Plan phase: any Approve/yes on a confirm answer → harness build (not another ask/plan loop).
    if meta.get("propose_build_plan") and not meta.get("awaiting_plan_revision"):
        for entry in recorded:
            if _plan_approval_is_approve(entry):
                return _route_plan_confirmed_build(
                    route,
                    meta,
                    message=message,
                    clarification_question=entry.get("question"),
                    thread_context=thread_context,
                )
            if _plan_approval_is_reject(entry):
                return _route_plan_revision(
                    route,
                    meta,
                    message=message,
                    revision_reason=entry.get("other_text"),
                )

    for entry in recorded:
        if _is_plan_approval_entry(entry, meta):
            continue
        if "no" in entry["selection_ids"] and len(entry["selection_ids"]) == 1:
            route["intent"] = "ask"
            route["enhanced_question"] = (
                "The user declined the proposed next action. Acknowledge briefly and ask what they want instead."
            )
            meta["wants_sample_run"] = False
            meta["edit_existing_workflow"] = False
            route["metadata"] = meta
            route["source"] = "clarification_declined"
            return route

    for entry in recorded:
        if not _is_plan_approval_entry(entry, meta):
            continue
        if _plan_approval_is_approve(entry):
            return _route_plan_confirmed_build(
                route,
                meta,
                message=message,
                clarification_question=entry.get("question"),
                thread_context=thread_context,
            )
        if _plan_approval_is_reject(entry):
            return _route_plan_revision(
                route,
                meta,
                message=message,
                revision_reason=entry.get("other_text"),
            )

    other_parts: list[str] = []
    for entry in recorded:
        if OTHER_OPTION_ID in entry["selection_ids"] and entry.get("other_text"):
            other_parts.append(entry["other_text"])
    if other_parts and not any(
        sid != OTHER_OPTION_ID
        for entry in recorded
        for sid in entry["selection_ids"]
    ):
        combined_other = "\n".join(other_parts)
        if gemini_configured() or adapter is not None:
            try:
                raw = (adapter or get_default_adapter()).chat_turn(
                    system_prompt=_CLARIFY_SYSTEM,
                    history=[],
                    user_turn=(
                        f"User originally said: {message}\n"
                        f"Proposed route was: {json.dumps(pending_route, default=str)[:800]}\n"
                        f"User clarification (Something else): {combined_other}\n\n"
                        "Return JSON with keys: intent, enhanced_question, metadata (object), "
                        "wants_sample_run (bool), edit_existing_workflow (bool)."
                    ),
                    temperature=0.0,
                    json_mode=True,
                )
                parsed = _extract_json(raw) or {}
                if parsed.get("intent"):
                    route["intent"] = str(parsed["intent"])
                if parsed.get("enhanced_question"):
                    route["enhanced_question"] = str(parsed["enhanced_question"])
                if isinstance(parsed.get("metadata"), dict):
                    meta.update(parsed["metadata"])
                route["metadata"] = meta
                route["source"] = "clarification_other"
                return route
            except Exception:
                pass
        route["intent"] = "ask"
        route["enhanced_question"] = combined_other
        route["metadata"] = meta
        route["source"] = "clarification_other"
        return route

    for entry in recorded:
        labels = entry.get("selection_labels") or []
        for i, sel in enumerate(entry["selection_ids"]):
            label = labels[i] if i < len(labels) else sel
            desc = ""
            if _selection_implies_build(sel, label, desc, entry.get("other_text")):
                answer = _format_answer_entry(entry)
                return _route_create_to_plan_phase(
                    route,
                    meta,
                    message=message,
                    answer=answer,
                    clarification_question=entry.get("question"),
                )

    for entry in recorded:
        labels = entry.get("selection_labels") or []
        for i, sel in enumerate(entry["selection_ids"]):
            label = labels[i] if i < len(labels) else sel
            if _selection_implies_list(sel, label, "", entry.get("other_text")):
                meta["clarification_resolved"] = True
                route["intent"] = "ask"
                route["enhanced_question"] = (
                    f"{eq}\n\nList saved and draft workflows from the database library "
                    f"(name, kind, last updated) and ask which one to open."
                )
                route["metadata"] = meta
                route["source"] = "clarification_list_workflows"
                return route

    for entry in recorded:
        labels = entry.get("selection_labels") or []
        for i, sel in enumerate(entry["selection_ids"]):
            label = labels[i] if i < len(labels) else sel
            if _selection_implies_load(sel, label, "", entry.get("other_text")):
                meta["clarification_resolved"] = True
                route["intent"] = "load"
                route["metadata"] = meta
                route["source"] = "clarification_confirmed_load"
                return route

    if meta.get("propose_build_plan"):
        for entry in recorded:
            if not _is_plan_approval_entry(entry, meta):
                continue
            if _plan_approval_is_approve(entry):
                return _route_plan_confirmed_build(
                    route,
                    meta,
                    message=message,
                    clarification_question=entry.get("question"),
                    thread_context=thread_context,
                )
            if _plan_approval_is_reject(entry):
                return _route_plan_revision(
                    route,
                    meta,
                    message=message,
                    revision_reason=entry.get("other_text"),
                )

    primary = answers[-1] if answers else {}
    sel_ids = primary.get("selection_ids") or ["yes"]
    labels = primary.get("selection_labels") or []
    return _resolve_clarification_selection_legacy(
        selection_id=str(sel_ids[0]),
        other_text=primary.get("other_text"),
        pending_route=route,
        message=message,
        thread_context=thread_context,
        has_workflow=has_workflow,
        canvas_workflow=canvas_workflow,
        clarification_kind=str(primary.get("kind") or "choice"),
        clarification_question=str(primary.get("question") or ""),
        selection_label=labels[0] if labels else None,
        selection_description=None,
        adapter=adapter,
    )


def resolve_clarification_selection(
    *,
    selection_id: str,
    other_text: str | None,
    pending_route: dict[str, Any],
    message: str,
    thread_context: str | None = None,
    has_workflow: bool = False,
    canvas_workflow: dict[str, Any] | None = None,
    clarification_kind: str = "confirm",
    clarification_question: str | None = None,
    selection_label: str | None = None,
    selection_description: str | None = None,
    adapter: GeminiAdapter | None = None,
) -> dict[str, Any]:
    """Map a single UI answer to a final route dict (same shape as /copilot/route)."""
    return resolve_clarification_answers(
        answers=[
            {
                "question": clarification_question or "",
                "kind": clarification_kind,
                "selection_ids": [selection_id],
                "other_text": other_text,
                "selection_labels": [selection_label] if selection_label else [],
            }
        ],
        pending_route=pending_route,
        message=message,
        thread_context=thread_context,
        has_workflow=has_workflow,
        canvas_workflow=canvas_workflow,
        adapter=adapter,
    )


def _resolve_clarification_selection_legacy(
    *,
    selection_id: str,
    other_text: str | None,
    pending_route: dict[str, Any],
    message: str,
    thread_context: str | None = None,
    has_workflow: bool = False,
    canvas_workflow: dict[str, Any] | None = None,
    clarification_kind: str = "confirm",
    clarification_question: str | None = None,
    selection_label: str | None = None,
    selection_description: str | None = None,
    adapter: GeminiAdapter | None = None,
) -> dict[str, Any]:
    sel = (selection_id or "").strip().lower()
    other = (other_text or "").strip()
    route = dict(pending_route or {})
    meta = dict(route.get("metadata") or {})
    pending_intent = str(route.get("intent") or "").strip().lower()

    def _record_clarification_answer(answer: str) -> None:
        answer = (answer or "").strip()
        if not answer:
            return
        meta["clarification_answer"] = answer
        if clarification_question:
            meta["clarification_question"] = clarification_question.strip()
        meta["clarification_resolved"] = True

    def _append_clarification_to_question(answer: str) -> None:
        eq = str(route.get("enhanced_question") or message).strip()
        route["enhanced_question"] = f"{eq}\n\nUser clarification: {answer.strip()}"

    if sel == "no":
        route["intent"] = "ask"
        route["enhanced_question"] = (
            "The user declined the proposed next action. Acknowledge briefly and ask what they want instead."
        )
        meta["wants_sample_run"] = False
        meta["edit_existing_workflow"] = False
        route["metadata"] = meta
        route["source"] = "clarification_declined"
        return route

    if sel == "other" and other:
        if gemini_configured() or adapter is not None:
            try:
                raw = (adapter or get_default_adapter()).chat_turn(
                    system_prompt=_CLARIFY_SYSTEM,
                    history=[],
                    user_turn=(
                        f"User originally said: {message}\n"
                        f"Proposed route was: {json.dumps(pending_route, default=str)[:800]}\n"
                        f"User clarification (Other): {other}\n\n"
                        "Return JSON with keys: intent, enhanced_question, metadata (object), "
                        "wants_sample_run (bool), edit_existing_workflow (bool)."
                    ),
                    temperature=0.0,
                    json_mode=True,
                )
                parsed = _extract_json(raw) or {}
                if parsed.get("intent"):
                    route["intent"] = str(parsed["intent"])
                if parsed.get("enhanced_question"):
                    route["enhanced_question"] = str(parsed["enhanced_question"])
                if isinstance(parsed.get("metadata"), dict):
                    meta.update(parsed["metadata"])
                if "wants_sample_run" in parsed:
                    meta["wants_sample_run"] = bool(parsed["wants_sample_run"])
                route["metadata"] = meta
                route["source"] = "clarification_other"
                return route
            except Exception:
                pass
        route["intent"] = "ask"
        route["enhanced_question"] = other
        route["metadata"] = meta
        route["source"] = "clarification_other"
        return route

    if sel == "yes" and clarification_kind == "confirm":
        if meta.get("propose_build_plan") and not meta.get("awaiting_plan_revision"):
            return _route_plan_confirmed_build(
                route,
                meta,
                message=message,
                clarification_question=clarification_question,
                thread_context=thread_context,
            )
        if _selection_implies_build(sel, selection_label, selection_description, other):
            answer = (selection_label or "Create workflow").strip()
            if selection_description:
                answer = f"{answer} — {selection_description}".strip(" —")
            return _route_create_to_plan_phase(
                route,
                meta,
                message=message,
                answer=answer,
                clarification_question=clarification_question,
            )
        if meta.get("wants_sample_run") or is_sample_run_next_step(
            *last_next_step_from_thread(thread_context or "")
        ):
            meta["wants_sample_run"] = True
            meta["edit_existing_workflow"] = False
            meta["clarification_resolved"] = True
            route["intent"] = "ask"
            route["metadata"] = meta
            route["source"] = "clarification_confirmed_run"
            return route
        if str(route.get("intent")) == "load":
            meta["clarification_resolved"] = True
            route["metadata"] = meta
            route["source"] = "clarification_confirmed_load"
            return route
        if meta.get("edit_existing_workflow") or str(route.get("intent")) == "build":
            meta["clarification_resolved"] = True
            route["intent"] = "build"
            route["metadata"] = meta
            route["source"] = "clarification_confirmed_build"
            return route

    if clarification_kind == "choice" and sel in ("a", "b", "c", "d"):
        label = (selection_label or sel).strip()
        desc = (selection_description or "").strip()
        answer = f"{label} — {desc}".strip(" —") if desc else label
        _record_clarification_answer(answer)
        _append_clarification_to_question(answer)

        if _selection_implies_build(sel, label, desc, other):
            return _route_create_to_plan_phase(
                route,
                meta,
                message=message,
                answer=answer,
                clarification_question=clarification_question,
            )
        if _selection_implies_load(sel, label, desc, other) and pending_intent == "load":
            meta["clarification_resolved"] = True
            route["intent"] = "load"
            route["metadata"] = meta
            route["source"] = "clarification_confirmed_load"
            return route

        sql_review = pending_intent == "query_run_data" and re.search(
            r"\bsql\b", (message or "").lower()
        )
        if sql_review:
            layer_hints = {
                "a": "Use run history / run_logs metadata only (workflow, status, dates, errors).",
                "b": "Use output row data from a selected run (SQL on exported node output).",
                "c": "First filter runs by metadata, then run SQL on that run's output dataset.",
                "d": "Follow the user's described approach.",
            }
            hint = layer_hints.get(sel, answer)
            route["enhanced_question"] = (
                f"{str(route.get('enhanced_question') or message).strip()}\n\nClarification: {hint}"
            )
            meta["wants_sql"] = True
            if sel == "a":
                meta["verification_plan"] = ["row_counts"]
            elif sel in ("b", "c"):
                meta["verification_plan"] = ["row_counts", "join_orphans"]
        elif pending_intent in ("explain_run", "explain_error"):
            route["intent"] = pending_intent
            meta.pop("wants_sql", None)
        else:
            route["intent"] = route.get("intent") or pending_intent or "ask"

        route["metadata"] = meta
        route["source"] = f"clarification_choice_{sel}"
        return route

    if clarification_kind == "choice" and sel not in ("yes", "no", "other"):
        label = (selection_label or sel).strip()
        desc = (selection_description or "").strip()
        answer = other or (f"{label} — {desc}".strip(" —") if desc else label)
        _record_clarification_answer(answer)
        _append_clarification_to_question(answer)
        if _selection_implies_build(sel, label, desc, other):
            return _route_create_to_plan_phase(
                route,
                meta,
                message=message,
                answer=answer,
                clarification_question=clarification_question,
            )
        if _selection_implies_load(sel, label, desc, other) and pending_intent == "load":
            meta["clarification_resolved"] = True
            route["intent"] = "load"
            route["metadata"] = meta
            route["source"] = "clarification_confirmed_load"
            return route
        if pending_intent in ("explain_run", "explain_error", "query_run_data"):
            route["intent"] = pending_intent
        route["metadata"] = meta
        route["source"] = f"clarification_choice_{sel}"
        return route

    meta["clarification_resolved"] = True
    route["metadata"] = meta
    route["source"] = "clarification_confirmed"
    return route
