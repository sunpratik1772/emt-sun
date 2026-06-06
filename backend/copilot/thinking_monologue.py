"""LLM-generated Sherpa thinking monologues (no template fallback)."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Iterator

from llm import gemini_configured, get_default_adapter

logger = logging.getLogger(__name__)

_THINKING_SYSTEM = """You write Sherpa's private "Thinking" monologue — a collapsed block shown briefly before the user-facing reply.

Write exactly 2–4 short lines, first person (I / I'll), active voice, separated by newlines.

GOOD (+) — write like this (adapt to the request; do not copy verbatim):
Auditing the good example workflows in backend/good_examples/studio_* to check for orphan nodes and ensure they run end to end.
Examining the JSON structure of each workflow. Unwired notes will be removed or moved into labels and config fields. Then I'll run end-to-end tests to verify generation works cleanly.

BAD (-) — NEVER write like this:
User wants Suggest and apply one concrete improvement to this workflow. 2-step pipeline should work. Drafting now.
User asked: "why did the join fail". I'll explain what's available.
User asked: "Review the latest run of…". I'll pull the latest run of Trade Anomaly Detection. No node logs yet — I'll work from what's available.

GOOD (+) for run review (explain_run):
Pulling the latest run log for Trade Anomaly Detection and Reporting.
I'll scan per-node row counts, join coverage, and the export step before suggesting one reliability fix.
Writing the run summary now.

Style rules:
- Vary line 1: Auditing…, Examining…, Tracing…, Checking…, Mapping…, Walking through…, Pulling up…, Starting with…
- Line 1 names the concrete task for THIS request (datasets, workflow names, integrations, verbs from their message).
- Line 2+ states what you will inspect, wire, validate, or change next — specific to the route and user message.
- NEVER echo the user message or Sherpa route chip text verbatim (no "User wants…", "User asked…", quoted slash-command bodies).
- NEVER write "N-step pipeline should work", "Standard pipeline", "a few nodes should cover it", or other vague step-count filler.
- Sound like an engineer thinking out loud, not a chatbot template.

Your output is shown to the user AND passed verbatim to the next Sherpa step. Treat every line as a binding plan.
- Include every explicit requirement (validation, failure branch, Outlook, improve existing workflow, schedule, etc.).
- If they name a workflow in quotes, use that exact name.
- If they are improving an existing canvas workflow, say you are extending it — not rebuilding from scratch.
- Mention datasets or actions only when the user mentioned them; do not invent a simpler load/join/export story.
- No internal node ids (csv_output, db_query), no harness jargon, no bullet lists, no markdown headers.
- Plain text only.

End with exactly one closing line chosen by route:
- build / load / automate / improve: "Drafting now."
- ask: "Drafting the answer now."
- explain_run: "Writing the run summary now."
- failure: "Writing the recovery plan now."
"""


@dataclass
class ThinkingMonologueContext:
    route: str
    user_message: str
    enhanced_question: str = ""
    workflow: dict[str, Any] | None = None
    edit_existing: bool = False
    workflow_name: str = ""
    datasets: tuple[str, ...] = field(default_factory=tuple)
    intent_actions: tuple[str, ...] = field(default_factory=tuple)
    blueprint_title: str = ""
    recent_errors: list[dict[str, Any]] | None = None
    run_log: list[dict[str, Any]] | None = None
    route_metadata: dict[str, Any] | None = None
    search_query: str = ""
    build_first: bool = False
    failure_payload: dict[str, Any] | None = None

    @classmethod
    def for_build(
        cls,
        user_message: str,
        intent: Any,
        blueprint: Any | None = None,
        *,
        current_workflow: dict[str, Any] | None = None,
    ) -> ThinkingMonologueContext:
        wf_name = str((current_workflow or {}).get("name") or "").strip()
        bp_title = str(getattr(blueprint, "title", "") or "").strip()
        return cls(
            route="build",
            user_message=(user_message or "").strip(),
            workflow=current_workflow,
            edit_existing=current_workflow is not None,
            workflow_name=wf_name,
            datasets=tuple(getattr(intent, "datasets", ()) or ()),
            intent_actions=tuple(getattr(intent, "actions", ()) or ()),
            blueprint_title=bp_title,
        )

    @classmethod
    def for_ask(
        cls,
        user_message: str,
        *,
        workflow: dict[str, Any] | None = None,
        recent_errors: list[dict[str, Any]] | None = None,
    ) -> ThinkingMonologueContext:
        return cls(
            route="ask",
            user_message=(user_message or "").strip(),
            workflow=workflow,
            workflow_name=str((workflow or {}).get("name") or "").strip(),
            recent_errors=recent_errors,
        )

    @classmethod
    def for_load(cls, message: str, *, query: str = "") -> ThinkingMonologueContext:
        return cls(
            route="load",
            user_message=(message or "").strip(),
            search_query=(query or message or "").strip(),
        )

    @classmethod
    def for_automate(
        cls,
        message: str,
        *,
        workflow: dict[str, Any] | None = None,
        build_first: bool = False,
    ) -> ThinkingMonologueContext:
        return cls(
            route="automate",
            user_message=(message or "").strip(),
            workflow=workflow,
            workflow_name=str((workflow or {}).get("name") or "").strip(),
            build_first=build_first,
        )

    @classmethod
    def for_failure(cls, user_request: str, payload: dict[str, Any]) -> ThinkingMonologueContext:
        return cls(
            route="failure",
            user_message=(user_request or "").strip(),
            failure_payload=payload,
        )

    @classmethod
    def for_explain_run(
        cls,
        user_message: str,
        workflow: dict[str, Any],
        run_log: list[dict[str, Any]],
        *,
        route_metadata: dict[str, Any] | None = None,
    ) -> ThinkingMonologueContext:
        meta = route_metadata or {}
        wf_name = str(workflow.get("name") or meta.get("workflow_name") or "").strip()
        return cls(
            route="explain_run",
            user_message=(user_message or "").strip(),
            workflow=workflow,
            workflow_name=wf_name,
            run_log=run_log,
            route_metadata=meta,
        )

    def format_user_turn(self) -> str:
        lines = [
            f"Route: {self.route}",
            f"User message:\n{self.user_message or '(empty)'}",
        ]
        if self.enhanced_question and self.enhanced_question.strip() != self.user_message.strip():
            lines.append(f"Normalized request:\n{self.enhanced_question.strip()}")
        if self.workflow_name:
            lines.append(f"Canvas workflow: {self.workflow_name}")
        if self.edit_existing:
            lines.append("Mode: edit/improve existing workflow on canvas")
        if self.datasets:
            lines.append(f"Datasets mentioned: {', '.join(self.datasets)}")
        if self.intent_actions:
            lines.append(f"Intent actions: {', '.join(self.intent_actions)}")
        if self.blueprint_title:
            lines.append(f"Matched blueprint: {self.blueprint_title}")
        if self.search_query:
            lines.append(f"Library search: {self.search_query}")
        if self.build_first:
            lines.append("Automation plan: build workflow first, then schedule")
        if self.recent_errors:
            lines.append(f"Recent errors: {len(self.recent_errors)}")
        if self.run_log is not None:
            ok = sum(1 for e in self.run_log if e.get("status") == "ok")
            err = sum(1 for e in self.run_log if e.get("status") == "error")
            lines.append(f"Run log: {len(self.run_log)} node(s), {ok} ok, {err} failed")
        if self.route_metadata:
            meta = {k: v for k, v in self.route_metadata.items() if v not in (None, "", [], {})}
            if meta:
                lines.append(f"Route metadata: {meta}")
        clar_q = (self.route_metadata or {}).get("clarification_question")
        clar_a = (self.route_metadata or {}).get("clarification_answer")
        if clar_q and clar_a:
            lines.append(f"Clarification Q: {clar_q}")
            lines.append(f"User clarification (binding): {clar_a}")
        if self.failure_payload:
            errors = self.failure_payload.get("validation_errors") or []
            smoke = (self.failure_payload.get("runtime_smoke_error") or "").strip()
            if errors:
                lines.append(f"Validation errors: {len(errors)}")
            if smoke:
                lines.append(f"Runtime smoke error: {smoke[:200]}")
        return "\n\n".join(lines)


_LAME_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^User wants\s+", re.I), ""),
    (re.compile(r"^The user wants\s+", re.I), ""),
    (re.compile(r"^User asked:\s*", re.I), ""),
    (re.compile(r"^The user asked:\s*", re.I), ""),
    (re.compile(r"\b\d+-step pipeline should work\.?", re.I), ""),
    (re.compile(r"\bStandard \d+-step pipeline should work\.?", re.I), ""),
    (re.compile(r"\ba few nodes should cover it\.?", re.I), ""),
)

_UNACCEPTABLE_RE = re.compile(
    r"user wants|user asked|pipeline should work|standard \d+-step|a few nodes should cover"
    r"|no node logs yet|i'll pull the latest run|then i'll suggest one concrete change",
    re.I,
)

_LAME_FIRST_LINE_RE = re.compile(
    r"^(?:load|export|filter|sort|join)\s+[\w.,\s→-]+\.?$",
    re.I,
)

_GOOD_OPENER_RE = re.compile(
    r"^(?:Auditing|Examining|Tracing|Checking|Mapping|Walking|Pulling|Starting|I'll|Searching|Building|Saving|Reviewing)",
    re.I,
)

_CLOSING_LINE_RE = re.compile(
    r"^(?:Drafting now|Drafting the answer now|Drafting the result now|"
    r"Writing the run summary now|Writing the recovery plan now)\.?$",
    re.I,
)


def _polish_thinking_monologue(text: str) -> str:
    """Strip template slop; drop empty lines after cleanup."""
    if not text:
        return text
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        for pattern, repl in _LAME_PATTERNS:
            line = pattern.sub(repl, line).strip()
        if not line:
            continue
        if re.match(r"^(load|export|filter)\s+[\w.,\s→-]+$", line, re.I) and "I'll" not in line:
            line = f"I'll {line[0].lower()}{line[1:] if len(line) > 1 else ''}."
        lines.append(line)
    return "\n".join(lines)


def _normalize_monologue(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r"^```(?:text|markdown)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    return _polish_thinking_monologue(t.strip())


def _is_unacceptable_monologue(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    if _UNACCEPTABLE_RE.search(t):
        return True
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    if len(lines) < 2:
        return True
    body_lines = [ln for ln in lines if not _CLOSING_LINE_RE.match(ln)]
    if len(body_lines) < 2:
        return True
    first = body_lines[0]
    if _LAME_FIRST_LINE_RE.match(first):
        return True
    if not _GOOD_OPENER_RE.search(first) and len(first.split()) <= 5:
        return True
    return False


def _call_llm(
    ctx: ThinkingMonologueContext,
    adapter: Any,
    *,
    temperature: float,
) -> str:
    raw = adapter.single_shot(
        ctx.format_user_turn(),
        system_prompt=_THINKING_SYSTEM,
        temperature=temperature,
        max_output_tokens=320,
    )
    return _normalize_monologue(raw)


_ROUTE_CLOSING: dict[str, str] = {
    "build": "Drafting now.",
    "load": "Drafting the result now.",
    "ask": "Drafting the answer now.",
    "automate": "Drafting now.",
    "explain_run": "Writing the run summary now.",
    "failure": "Writing the recovery plan now.",
}


def _snip(text: str, limit: int = 72) -> str:
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    return t[: limit - 1].rstrip() + "…"


def _context_derived_monologue(ctx: ThinkingMonologueContext) -> str:
    """Structured fallback when LLM is off or unusable — never parrots slash-command chip text."""
    route = ctx.route
    closing = _ROUTE_CLOSING.get(route, "Drafting now.")
    lines: list[str] = []

    if route == "build":
        if ctx.edit_existing and ctx.workflow_name:
            lines.append(
                f'Examining **{ctx.workflow_name}** on the canvas — extending it in place, not rebuilding.'
            )
        elif ctx.datasets:
            ds = ", ".join(ctx.datasets[:3])
            lines.append(f"Mapping nodes and connectors for {ds}.")
        elif ctx.blueprint_title:
            lines.append(f"Adapting the {ctx.blueprint_title} blueprint skeleton to this request.")
        else:
            lines.append("Mapping datasets, transforms, and terminal outputs for this build.")
        if ctx.intent_actions:
            actions = ", ".join(str(a) for a in ctx.intent_actions[:4])
            lines.append(f"I'll wire {actions} next, then validate the DAG end to end.")
        else:
            lines.append("I'll keep the graph minimal and validate wiring before drafting.")
    elif route == "load":
        query = _snip(ctx.search_query or "saved workflows", 64)
        lines.append("Searching the workflow library for the closest canvas match.")
        lines.append(f"I'll open the best hit for {query!r} and verify nodes load cleanly.")
    elif route == "ask":
        if ctx.workflow_name:
            lines.append(f"Checking **{ctx.workflow_name}** and recent canvas errors against their question.")
        elif ctx.recent_errors:
            lines.append("Tracing recent canvas errors and ranking recovery options.")
        else:
            lines.append("Checking what's on the canvas and what Studio can do here.")
        lines.append("I'll outline the blocker and the fastest next step.")
    elif route == "automate":
        wf = ctx.workflow_name or "the canvas workflow"
        if ctx.build_first:
            lines.append(f"Building **{wf}** first, then saving and attaching a schedule.")
        else:
            lines.append(f"Saving **{wf}** and parsing the schedule from their automation request.")
        lines.append("I'll confirm timing and trigger wiring before drafting.")
    elif route == "explain_run":
        wf = ctx.workflow_name or "this workflow"
        if ctx.run_log:
            ok = sum(1 for e in ctx.run_log if e.get("status") == "ok")
            err = sum(1 for e in ctx.run_log if e.get("status") == "error")
            lines.append(
                f"Pulling the latest run of **{wf}** — {len(ctx.run_log)} step(s), "
                f"{ok} ok" + (f", {err} failed." if err else ".")
            )
            lines.append("I'll scan row counts, join coverage, and exports before suggesting one reliability fix.")
        else:
            lines.append(f"Checking run history for **{wf}** — nothing in memory or the database yet.")
            lines.append("I'll explain what's missing and how to capture logs on the next run.")
    elif route == "failure":
        payload = ctx.failure_payload or {}
        errors = payload.get("validation_errors") or []
        lines.append("Tracing why generation did not produce a runnable workflow.")
        if errors:
            lines.append(f"I'll walk through {len(errors)} validation issue(s) and the smallest recovery patch.")
        else:
            lines.append("I'll inspect validation and smoke output for the smallest recovery patch.")
    else:
        lines.append("Examining the request and canvas context.")
        lines.append("I'll plan the next concrete step before drafting.")

    lines.append(closing)
    return "\n".join(lines)


def _try_llm_monologue(
    ctx: ThinkingMonologueContext,
    adapter: Any | None,
) -> str:
    """Best-effort LLM monologue; empty when Gemini is off and no adapter was injected."""
    if not gemini_configured() and adapter is None:
        return ""
    ad = adapter or get_default_adapter()
    temps = (0.58, 0.72, 0.85)
    last = ""
    for temp in temps:
        try:
            text = _call_llm(ctx, ad, temperature=temp)
            last = text
            if text and not _is_unacceptable_monologue(text):
                return text
        except Exception as exc:
            logger.warning("LLM thinking monologue attempt failed (temp=%s): %s", temp, exc)
            last = ""
    return ""


def generate_thinking_monologue(
    ctx: ThinkingMonologueContext,
    adapter: Any | None = None,
) -> str:
    """LLM thinking monologue; structured context fallback guarantees non-empty output."""
    text = _try_llm_monologue(ctx, adapter)
    if text:
        return text
    derived = _context_derived_monologue(ctx)
    if not gemini_configured() and adapter is None:
        logger.info("Gemini unavailable — using context-derived thinking monologue")
    else:
        logger.warning("LLM thinking unusable after retries — using context-derived monologue")
    return derived


def collect_thinking_monologue(
    ctx: ThinkingMonologueContext,
    adapter: Any | None = None,
) -> str:
    """Return the final thinking monologue text (for downstream generation prompts)."""
    last = ""
    for last in iter_thinking_monologue_updates(ctx, adapter=adapter):
        pass
    return last


def iter_thinking_monologue_updates(
    ctx: ThinkingMonologueContext,
    adapter: Any | None = None,
) -> Iterator[str]:
    """Yield progressively longer monologue text for streaming UI typewriter."""
    accumulated = ""
    if gemini_configured() or adapter is not None:
        try:
            ad = adapter or get_default_adapter()
            for chunk in ad.chat_turn_stream(
                system_prompt=_THINKING_SYSTEM,
                history=[],
                user_turn=ctx.format_user_turn(),
                temperature=0.58,
                json_mode=False,
            ):
                accumulated += chunk
                normalized = _normalize_monologue(accumulated)
                if normalized and not _is_unacceptable_monologue(normalized):
                    yield normalized
        except Exception as exc:
            logger.warning("LLM thinking stream failed: %s", exc)

    final = _normalize_monologue(accumulated)
    if _is_unacceptable_monologue(final):
        final = _try_llm_monologue(ctx, adapter)
    if final:
        yield final
        return

    yield _context_derived_monologue(ctx)
