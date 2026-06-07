"""Copilot and NodeSpec-facing endpoints.

Router map for newcomers:
  * POST /copilot/chat              free-form multi-turn chat
  * POST /copilot/generate          blocking workflow draft/repair
  * POST /copilot/generate/stream   SSE workflow draft/repair timeline
  * GET  /copilot/skills            skill index for the prompt builder
  * GET  /copilot/skills/{id}       skill body

This module also owns `contracts_router`, mounted at top level from
`app.main`, for historical API compatibility:
  * GET /data_sources
  * GET /contracts
  * GET /node-manifest

The important architectural point: Studio should learn node behavior from
the live NodeSpec registry (`/node-manifest`), not from frontend constants.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth_deps import feature_guard
from fastapi.responses import StreamingResponse

from ..schemas import (
    CopilotAutomateRequest,
    CopilotLoadRequest,
    CopilotChatRequest,
    CopilotClassifyRequest,
    CopilotClassifyResponse,
    CopilotClarifyResolveRequest,
    CopilotRouteMetadata,
    CopilotResolveContextRequest,
    CopilotGenerateRequest,
    CopilotExplainRunRequest,
    RunLogQueryRequest,
    SherpaClarificationOption,
    SherpaClarificationPayload,
    SherpaClarificationQuestionPayload,
)
from .library import append_audit_log
from ..deps import CONTRACTS_PATH, SKILLS_DIR, get_copilot
from ..database import save_draft_db, list_recent_run_workflow_names
from copilot.automation_agent import run_automation_flow_stream
from copilot.workflow_loader import run_workflow_load_stream
from copilot.run_resolver import resolve_run_context
from copilot.sherpa_context import resolve_sherpa_context

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/copilot", tags=["copilot"])


def _thread_messages_payload(req: Any) -> list[dict] | None:
    raw = getattr(req, "thread_messages", None)
    if not raw:
        return None
    return [{"role": m.role, "content": m.content} for m in raw]


def _resolve_thread_context(
    cp: Any,
    req: Any,
    *,
    db_messages: list[dict] | None = None,
) -> tuple[list[dict[str, str]], str]:
    history = cp.resolve_session_thread(
        getattr(req, "session_id", None),
        thread_messages=_thread_messages_payload(req),
        db_messages=db_messages,
    )
    return history, cp.thread_context_from_history(history)


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    s = _SLUG_RE.sub("-", (name or "draft").lower()).strip("-")
    return s or "draft"


def _trigger_bg_refresh() -> None:
    """Trigger background refresh of understand-anything artifacts asynchronously."""
    import threading
    from app.understand_anything import refresh_artifacts
    try:
        threading.Thread(target=refresh_artifacts, kwargs={"mode": "all"}).start()
    except Exception:
        logger.exception("Failed to trigger background UA refresh")


def _autosave_draft(dag: dict[str, Any]) -> str | None:
    """Persist a Copilot-generated workflow to the drafts table."""
    try:
        from ..request_context import get_current_user_id

        slug = _slugify(dag.get("name") or dag.get("workflow_id") or "draft")
        filename = f"{slug}-{int(time.time())}.json"
        save_draft_db(
            filename=filename,
            workflow_id=dag.get("workflow_id"),
            name=dag.get("name"),
            description=dag.get("description"),
            workflow_data=json.dumps(dag),
            user_id=get_current_user_id(),
        )
        _trigger_bg_refresh()
        return filename
    except Exception:
        logger.exception("Failed to auto-save draft")
        return None


@router.post("/chat")
def copilot_chat(req: CopilotChatRequest) -> dict:
    """Copilot chat.

    Multi-turn history is scoped by `session_id`. Requests without a
    session_id are deliberately stateless so the process-wide cached
    WorkflowCopilot cannot leak chat context between users.
    """
    from ..user_scope import SEED_USER_ID

    _bind_copilot_memory(SEED_USER_ID)
    cp = get_copilot()
    if req.reset_history:
        cp.reset(session_id=req.session_id)
    try:
        reply = cp.chat(
            req.message,
            session_id=req.session_id,
            current_workflow=req.current_workflow,
            recent_errors=req.recent_errors,
        )
        append_audit_log({
            "actor": "user",
            "action": "copilot.chat",
            "detail": (req.message or "")[:140],
        })
        return {"reply": reply}
    except Exception as exc:
        append_audit_log({
            "actor": "user",
            "action": "copilot.chat",
            "status": "error",
            "detail": str(exc)[:200],
        })
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/resolve-context")
def copilot_resolve_context(req: CopilotResolveContextRequest) -> dict:
    """Resolve workflow + run_log for Sherpa explain/build handlers."""
    ctx = resolve_sherpa_context(
        req.route_metadata,
        canvas_workflow=req.current_workflow,
        canvas_run_log=req.run_log,
        canvas_run_result=req.run_result,
        canvas_run_error=req.run_error,
    )
    return ctx


def _route_metadata_from_dict(meta: dict[str, Any]) -> CopilotRouteMetadata:
    return CopilotRouteMetadata(
        workflow_name=meta.get("workflow_name"),
        run_selector=meta.get("run_selector"),
        run_id=meta.get("run_id"),
        run_status_filter=meta.get("run_status_filter"),
        error_message=meta.get("error_message"),
        node_id=meta.get("node_id"),
        topics=list(meta.get("topics") or []),
        wants_sql=bool(meta.get("wants_sql")),
        edit_existing_workflow=bool(meta.get("edit_existing_workflow")),
        wants_sample_run=bool(meta.get("wants_sample_run")),
        slash_route=meta.get("slash_route"),
        suggested_sql=meta.get("suggested_sql"),
        verification_plan=list(meta.get("verification_plan") or []) or None,
        clarification_resolved=bool(meta.get("clarification_resolved")),
        propose_build_plan=bool(meta.get("propose_build_plan")),
        build_plan_confirmed=bool(meta.get("build_plan_confirmed")),
        original_user_request=meta.get("original_user_request"),
        awaiting_plan_revision=bool(meta.get("awaiting_plan_revision")),
        plan_revision_reason=meta.get("plan_revision_reason"),
        sherpa_disposition=meta.get("sherpa_disposition"),
        disposition_confidence=meta.get("disposition_confidence"),
        thinking_preview=meta.get("thinking_preview"),
        propose_fix_plan=bool(meta.get("propose_fix_plan")),
    )


def _classify_response_from_result(
    result: Any,
    *,
    message: str,
    thread_context: str | None,
    has_workflow: bool,
    canvas_workflow: dict[str, Any] | None,
    skip_clarification: bool = False,
) -> CopilotClassifyResponse:
    from copilot.intent_clarification import assess_route_clarification
    from copilot.intent_layer import resolve_sherpa_disposition
    from app.schemas import SherpaDispositionPayload

    result, disposition = resolve_sherpa_disposition(
        result,
        message,
        thread_context=thread_context,
        has_workflow=has_workflow,
        canvas_workflow=canvas_workflow,
    )
    meta = result.metadata or {}
    clarification = None
    if not skip_clarification:
        clarification = assess_route_clarification(
        result,
        message,
        thread_context=thread_context,
        has_workflow=has_workflow,
        canvas_workflow=canvas_workflow,
        )
    clar_payload: SherpaClarificationPayload | None = None
    if clarification and clarification.needed:
        clar_payload = SherpaClarificationPayload(
            needed=True,
            kind=clarification.kind,
            question=clarification.question,
            options=[
                SherpaClarificationOption(
                    id=o.id,
                    label=o.label,
                    description=o.description,
                )
                for o in clarification.options
            ],
            default_option_id=clarification.default_option_id,
            questions=[
                SherpaClarificationQuestionPayload(
                    id=q.id,
                    kind=q.kind,
                    question=q.question,
                    options=[
                        SherpaClarificationOption(
                            id=o.id,
                            label=o.label,
                            description=o.description,
                        )
                        for o in q.options
                    ],
                    default_option_id=q.default_option_id,
                    allow_multiple=q.allow_multiple,
                )
                for q in clarification.questions
            ],
            reason=clarification.reason,
        )
    thinking = str(meta.get("thinking_preview") or disposition.thinking or "").strip()
    return CopilotClassifyResponse(
        intent=result.intent,
        reason=result.reason,
        source=result.source,
        enhanced_question=result.enhanced_question or message,
        keywords=list(result.keywords or ()),
        metadata=_route_metadata_from_dict(meta),
        clarification=clar_payload,
        disposition=SherpaDispositionPayload(
            kind=disposition.kind,
            thinking=disposition.thinking,
            confidence=disposition.confidence,
            reason=disposition.reason,
        ),
        thinking_preview=thinking or None,
    )


@router.post("/classify", response_model=CopilotClassifyResponse)
@router.post("/route", response_model=CopilotClassifyResponse)
def copilot_classify(req: CopilotClassifyRequest) -> CopilotClassifyResponse:
    """Route a copilot message via LLM structured output (intent + enhanced_question + metadata)."""
    cp = get_copilot()
    try:
        _, thread_context = _resolve_thread_context(cp, req)
        from ..request_context import get_current_user_id

        recent_names = list_recent_run_workflow_names(5, get_current_user_id())
        result = cp.classify_intent(
            req.message,
            has_workflow=req.has_workflow,
            workflow_name=req.workflow_name,
            has_run_log=req.has_run_log,
            run_id=req.run_id,
            run_workflow_name=req.run_workflow_name,
            recent_errors=req.recent_errors,
            thread_context=thread_context or None,
            recent_run_workflows=recent_names,
            canvas_workflow=req.current_workflow,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    from copilot.build_plan_gate import gate_route_to_build_plan_phase

    result = gate_route_to_build_plan_phase(result, req.message)
    # Intent layer runs inside _classify_response_from_result (after plan gate).
    return _classify_response_from_result(
        result,
        message=req.message,
        thread_context=thread_context,
        has_workflow=req.has_workflow,
        canvas_workflow=req.current_workflow,
    )


@router.post("/clarify/resolve", response_model=CopilotClassifyResponse)
def copilot_clarify_resolve(req: CopilotClarifyResolveRequest) -> CopilotClassifyResponse:
    """Apply the user's clarification answer and return the executable route."""
    from copilot.intent_clarification import (
        resolve_clarification_answers,
        resolve_clarification_selection,
    )
    from copilot.llm_router import finalize_sherpa_route, SherpaRoute

    cp = get_copilot()
    try:
        _, thread_context = _resolve_thread_context(cp, req)
        if req.answers:
            answer_payloads = [
                {
                    "question_id": a.question_id,
                    "question": a.question,
                    "kind": a.kind,
                    "selection_ids": list(a.selection_ids),
                    "other_text": a.other_text,
                    "selection_labels": list(a.selection_labels),
                }
                for a in req.answers
            ]
            resolved = resolve_clarification_answers(
                answers=answer_payloads,
                pending_route=req.pending_route,
                message=req.message,
                thread_context=thread_context or None,
                has_workflow=req.has_workflow,
                canvas_workflow=req.current_workflow,
            )
        else:
            resolved = resolve_clarification_selection(
                selection_id=req.selection_id or "yes",
                other_text=req.other_text,
                pending_route=req.pending_route,
                message=req.message,
                thread_context=thread_context or None,
                has_workflow=req.has_workflow,
                canvas_workflow=req.current_workflow,
                clarification_kind=req.clarification_kind or "confirm",
                clarification_question=req.clarification_question,
                selection_label=req.selection_label,
                selection_description=req.selection_description,
            )
        route = finalize_sherpa_route(
            SherpaRoute(
                intent=str(resolved.get("intent") or "ask"),
                reason=str(resolved.get("reason") or "Clarification resolved"),
                enhanced_question=str(resolved.get("enhanced_question") or req.message),
                keywords=tuple(),
                metadata=dict(resolved.get("metadata") or {}),
                source=str(resolved.get("source") or "clarification"),
            ),
            message=req.message,
            thread_context=thread_context,
            canvas_workflow=req.current_workflow,
        )
        from copilot.build_plan_gate import gate_route_to_build_plan_phase

        route = gate_route_to_build_plan_phase(route, req.message)
        return _classify_response_from_result(
            route,
            message=req.message,
            thread_context=thread_context,
            has_workflow=req.has_workflow,
            canvas_workflow=req.current_workflow,
            skip_clarification=True,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/routes")
def copilot_slash_routes(
    has_workflow: bool = False,
    has_run_log: bool = False,
    has_errors: bool = False,
) -> dict:
    """Optional Sherpa slash commands and contextual chip suggestions."""
    from copilot.sherpa_routes import list_sherpa_routes

    return list_sherpa_routes(
        has_workflow=has_workflow,
        has_run_log=has_run_log,
        has_errors=has_errors,
    )


# Tunable: how big each SSE chunk is (in *tokens*, where a token is
# whatever `re.split(r"(\s+)")` returns — words + intervening whitespace).
# Smaller = smoother typewriter, more network frames; larger = chunkier.
_STREAM_CHUNK_TOKENS = 4
# Inter-chunk pacing. 0 = flush as fast as the client can read; small
# delay makes the typewriter feel deliberate without being slow.
_STREAM_CHUNK_DELAY_S = 0.018


@router.post("/chat/stream")
def copilot_chat_stream(req: CopilotChatRequest) -> StreamingResponse:
    """SSE-streamed chat reply with the same thinking + text frames as build/run review."""
    cp = get_copilot()
    if req.reset_history:
        cp.reset(session_id=req.session_id)

    def event_source():
        from copilot.thinking_monologue import ThinkingMonologueContext
        from copilot.next_action import ensure_ask_next_action_footer
        from copilot.thinking_sse import yield_llm_thinking_monologue

        try:
            ctx = ThinkingMonologueContext.for_ask(
                req.message,
                workflow=req.current_workflow,
                recent_errors=req.recent_errors,
            )
            monologue = ""
            for frame in yield_llm_thinking_monologue(ctx):
                monologue = str(frame.get("detail") or monologue)
                yield "data: " + json.dumps(frame) + "\n\n"

            yield "data: " + json.dumps({
                "type": "thinking",
                "step": "Drafting your answer",
                "status": "running",
            }) + "\n\n"

            reply = cp.chat(
                req.message,
                session_id=req.session_id,
                current_workflow=req.current_workflow,
                recent_errors=req.recent_errors,
                planning_monologue=monologue,
            ) or ""
            from copilot.build_plan_gate import message_requests_build_plan

            if not message_requests_build_plan(
                req.message,
                propose_build_plan=bool(getattr(req, "propose_build_plan", False)),
            ):
                reply = ensure_ask_next_action_footer(
                    reply,
                    user_message=req.message,
                    workflow=req.current_workflow,
                )

            yield "data: " + json.dumps({
                "type": "thinking",
                "step": "Drafting your answer",
                "status": "done",
            }) + "\n\n"
        except Exception as exc:
            logger.exception("Copilot chat stream failed")
            append_audit_log({
                "actor": "user",
                "action": "copilot.chat",
                "status": "error",
                "detail": str(exc)[:200],
            })
            yield "data: " + json.dumps({"type": "error", "message": str(exc)}) + "\n\n"
            return

        append_audit_log({
            "actor": "user",
            "action": "copilot.chat",
            "detail": (req.message or "")[:140],
        })

        yield "data: " + json.dumps({"type": "text_start"}) + "\n\n"
        tokens = re.split(r"(\s+)", reply)
        for i in range(0, len(tokens), _STREAM_CHUNK_TOKENS):
            piece = "".join(tokens[i : i + _STREAM_CHUNK_TOKENS])
            if not piece:
                continue
            yield "data: " + json.dumps({"type": "text_chunk", "chunk": piece}) + "\n\n"
            if _STREAM_CHUNK_DELAY_S:
                time.sleep(_STREAM_CHUNK_DELAY_S)
        yield "data: " + json.dumps({"type": "text_end"}) + "\n\n"
        yield "data: " + json.dumps({"type": "done", "success": True}) + "\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/generate")
def copilot_generate(req: CopilotGenerateRequest) -> dict:
    """Generate a workflow DAG JSON with N critic iterations.

    Successfully generated workflows are auto-persisted to `drafts/` so
    they show up in the Drafts section of the workflow drawer — the user
    can then promote one to a Saved workflow via Save-as.

    When the frontend attaches `current_workflow` (and optionally
    `recent_errors`) the planner runs in edit-mode: it sees the DAG
    already loaded in the canvas plus any validator/runtime failures
    and produces a targeted fix rather than a greenfield workflow.
    """
    from ..user_scope import SEED_USER_ID

    _bind_copilot_memory(SEED_USER_ID)
    try:
        cp = get_copilot()
        _, thread_context = _resolve_thread_context(cp, req)
        result = cp.generate_with_critic(
            req.prompt,
            iterations=req.critic_iterations,
            current_workflow=req.current_workflow,
            recent_errors=req.recent_errors,
            selected_node_id=req.selected_node_id,
            compiler_mode=(req.compiler_mode or "harness"),
            session_id=req.session_id,
            thread_messages=_thread_messages_payload(req),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if result.get("success") and result.get("workflow"):
        draft_filename = _autosave_draft(result["workflow"])
        if draft_filename:
            result["draft_filename"] = draft_filename
    append_audit_log({
        "actor": "user",
        "action": "copilot.generate",
        "status": "ok" if result.get("success") else "error",
        "detail": (req.prompt or "")[:140],
    })
    return result


@router.post("/generate/stream")
def copilot_generate_stream(req: CopilotGenerateRequest) -> StreamingResponse:
    """
    Stream workflow generation as Server-Sent Events.
    Events: thinking → workflow_created → text_chunk → done (harness UI).

    Accepts the same optional edit-mode fields as `/copilot/generate`.
    """
    def event_source():
        from ..user_scope import SEED_USER_ID

        _bind_copilot_memory(SEED_USER_ID)
        try:
            cp = get_copilot()
            thread_payload = _thread_messages_payload(req)
            for event in cp.generate_with_critic_stream(
                req.prompt,
                iterations=req.critic_iterations,
                current_workflow=req.current_workflow,
                recent_errors=req.recent_errors,
                selected_node_id=req.selected_node_id,
                compiler_mode=(req.compiler_mode or "harness"),
                session_id=req.session_id,
                thread_messages=thread_payload,
            ):
                # Hitch a draft auto-save to the terminal "complete" event
                # so the drawer's Drafts section reflects the new workflow
                # the instant streaming finishes.
                wf = event.get("workflow")
                if event.get("type") == "workflow_created" and wf:
                    draft_filename = _autosave_draft(wf)
                    if draft_filename:
                        event = {**event, "draft_filename": draft_filename}
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:
            logger.exception("Copilot stream failed")
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/automate/stream")
def copilot_automate_stream(req: CopilotAutomateRequest) -> StreamingResponse:
    """Create a scheduled automation from NL — optionally build workflow first, then test run."""

    def event_source():
        cp = get_copilot()
        _, thread_context = _resolve_thread_context(cp, req)
        automation_reply = ""

        def _generate(prompt: str, *, current_workflow: dict | None) -> dict:
            return cp.generate_with_critic(
                prompt,
                iterations=req.critic_iterations,
                current_workflow=current_workflow,
                session_id=req.session_id,
                thread_messages=_thread_messages_payload(req),
            )

        def _generate_stream(prompt: str, *, current_workflow: dict | None):
            yield from cp.generate_with_critic_stream(
                prompt,
                iterations=req.critic_iterations,
                current_workflow=current_workflow,
                session_id=req.session_id,
                thread_messages=_thread_messages_payload(req),
            )

        try:
            for event in run_automation_flow_stream(
                message=req.message,
                current_workflow=req.current_workflow,
                generate_workflow=_generate,
                generate_workflow_stream=_generate_stream,
                thread_context=thread_context or None,
            ):
                if event.get("type") == "text_chunk" and event.get("chunk"):
                    automation_reply += str(event["chunk"])
                yield f"data: {json.dumps(event)}\n\n"
            if req.session_id:
                cp.record_thread_turn(
                    req.session_id,
                    user_message=req.message,
                    assistant_message=automation_reply.strip()
                    or "Created a scheduled automation for the workflow.",
                )
            append_audit_log({
                "actor": "user",
                "action": "copilot.automate",
                "status": "ok",
                "detail": (req.message or "")[:140],
            })
        except Exception as exc:
            logger.exception("Copilot automate stream failed")
            append_audit_log({
                "actor": "user",
                "action": "copilot.automate",
                "status": "error",
                "detail": str(exc)[:200],
            })
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/load/stream")
def copilot_load_stream(req: CopilotLoadRequest) -> StreamingResponse:
    """Search saved workflows and load or disambiguate (≤3 matches)."""

    def event_source():
        cp = get_copilot()
        load_reply = ""
        try:
            for event in run_workflow_load_stream(req.message):
                if event.get("type") == "text_chunk" and event.get("chunk"):
                    load_reply += str(event["chunk"])
                yield f"data: {json.dumps(event)}\n\n"
            if req.session_id:
                cp.record_thread_turn(
                    req.session_id,
                    user_message=req.message,
                    assistant_message=load_reply.strip() or "Workflow load finished.",
                )
            append_audit_log({
                "actor": "user",
                "action": "copilot.load",
                "status": "ok",
                "detail": (req.message or "")[:140],
            })
        except Exception as exc:
            logger.exception("Copilot load stream failed")
            append_audit_log({
                "actor": "user",
                "action": "copilot.load",
                "status": "error",
                "detail": str(exc)[:200],
            })
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/explain-run/stream")
def copilot_explain_run_stream(req: CopilotExplainRunRequest) -> StreamingResponse:
    """Stream a data-focused post-run summary for the Copilot chat panel."""

    def event_source():
        try:
            for event in get_copilot().explain_run_stream(
                req.workflow,
                req.run_log,
                req.run_result,
                req.run_error,
                req.user_message,
                req.suggested_sql,
                req.route_metadata,
            ):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:
            logger.exception("Copilot explain-run stream failed")
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/example-prompts")
def example_prompts(
    first_name: str | None = None,
    period: str | None = None,
) -> dict:
    """Generate context-aware example prompts and dashboard welcome subline.

    Returns:
      - build_prompts / ask_prompts: side panel suggestion chips
      - dashboard_subline: one LLM question under the home greeting
    """
    from copilot.dashboard_subline import generate_dashboard_subline
    from copilot.prompt_examples import generate_example_prompts

    out = generate_example_prompts()
    sub = generate_dashboard_subline(
        first_name=(first_name or "").strip(),
        period=(period or "").strip(),
    )
    out["dashboard_subline"] = sub["subline"]
    out["dashboard_subline_from_ai"] = sub["from_ai"]
    return out


@router.get("/dashboard-subline")
def dashboard_subline(
    first_name: str | None = None,
    period: str | None = None,
) -> dict:
    """One LLM-generated welcome question (also included on /example-prompts)."""
    from copilot.dashboard_subline import generate_dashboard_subline

    return generate_dashboard_subline(
        first_name=(first_name or "").strip(),
        period=(period or "").strip(),
    )


@router.get("/skills")
def list_skills() -> dict:
    """Return available skill file names and descriptions."""
    return {"skills": _skill_rows()}


def _skill_rows() -> list[dict]:
    skills: list[dict] = []
    if SKILLS_DIR.exists():
        for f in sorted(SKILLS_DIR.glob("*.md")):
            content = f.read_text()
            first_line = next((l for l in content.splitlines() if l.startswith("# ")), f.stem)
            skills.append(
                {
                    "id": f.stem,
                    "name": first_line.lstrip("# "),
                    "filename": f.name,
                }
            )
    return skills


@router.get("/guardrails")
def get_guardrails() -> dict:
    """
    Return the active authoring constraints that Copilot generation must obey.

    This is UI-facing: it lets the Plan panel show the same boundaries the
    backend prompt/validator uses (live NodeSpecs, data-source YAML, skill files,
    and host capabilities like whether custom script execution is enabled).
    """
    from connectors import get_registry
    from engine.registry import studio_manifest

    manifest = studio_manifest()
    data_sources = get_registry().to_json().get("sources", [])
    upload_enabled = os.environ.get("DBSHERPA_ALLOW_UPLOAD_SCRIPT", "").lower() in {"1", "true", "yes"}
    return {
        "nodes": [
            {
                "type_id": n["type_id"],
                "description": n["description"],
                "section": n.get("palette_group"),
            }
            for n in manifest["nodes"]
        ],
        "data_sources": data_sources,
        "skills": _skill_rows(),
        "capabilities": {
            "upload_script_enabled": upload_enabled,
            "allowed_signal_modes": ["configure"] + (["upload_script"] if upload_enabled else []),
            "builtin_signal_types": ["FRONT_RUNNING", "WASH_TRADE", "SPOOFING", "LAYERING"],
        },
        "rules": [
            "Only use node types and parameters from live NodeSpec.",
            "Only use data-source names and columns declared in metadata YAML.",
            "Use scenario logic from skills; unsupported scenarios should be narrowed to supported sources/nodes.",
            (
                "Custom Python signal scripts are allowed."
                if upload_enabled
                else "Custom Python signal scripts are disabled; use built-in SIGNAL_CALCULATOR configure mode."
            ),
        ],
    }


@router.get("/skills/{skill_id}")
def get_skill(skill_id: str) -> dict:
    """Return full content of a skill file."""
    safe = f"{skill_id}.md"
    if safe != f"{Path(safe).name}":
        raise HTTPException(status_code=400, detail="skill_id must be a bare filename stem")
    path = SKILLS_DIR / safe
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    return {"id": skill_id, "content": path.read_text()}


# Contracts live at the top level (not under /copilot) for historical
# reasons, but the copilot is the primary consumer so they're grouped here.
# We mount this via a second router in main.py.
contracts_router = APIRouter(tags=["copilot"])


@contracts_router.get("/data_sources")
def get_data_sources() -> dict:
    """
    Return the declarative dataset catalog. Each entry lists columns
    and their types/semantic tags as loaded from
    `backend/connectors/metadata/*.yaml`. See `backend/connectors/catalog.py` for the shape.
    """
    from connectors import get_registry

    return get_registry().to_json()


@contracts_router.get("/contracts")
def get_contracts() -> dict:
    """
    Return node I/O contracts, generated live from the registry.

    Serving this dynamically (rather than the old static
    `node_contracts.json`) means: adding a new node via
    `engine/nodes/<type>.py` is immediately visible to the
    frontend palette + copilot prompt builder on the next
    request — no script to run, no artifact to commit.

    If `CONTRACTS_PATH` still exists, we merge it with the live document.
    Dynamic registry entries win on duplicate node ids, so a newly edited
    NodeSpec is what the UI/copilot sees on the next request.
    """
    from engine.registry import contracts_document

    doc = contracts_document()
    if CONTRACTS_PATH.exists():
        try:
            with open(CONTRACTS_PATH) as f:
                static_doc = json.load(f)
            # Merge: dynamic wins on duplicates.
            merged_nodes = {**static_doc.get("nodes", {}), **doc["nodes"]}
            doc = {**static_doc, **doc, "nodes": merged_nodes}
        except Exception:  # pragma: no cover - defensive
            pass
    return doc


@contracts_router.get("/node-manifest")
def get_node_manifest(_user_id: str = Depends(feature_guard("node_palette"))) -> dict:
    """
    Live NodeSpec snapshot for the Studio: palette sections, node list with
    UI metadata, typed ports/params, and contracts. The UI fetches this on
    load (and on manual refresh) so new backend nodes appear without
    regenerating frontend artifacts.
    """
    from engine.registry import studio_manifest

    return studio_manifest()


# --- CHAT HISTORY DATABASE SUPPORT ---

def _bind_copilot_memory(user_id: str) -> None:
    from ..request_context import set_current_user_id

    set_current_user_id(user_id)
    get_copilot()._memory.bind_user(user_id)


async def get_user_id(request: Request) -> str:
    cookie_token = request.cookies.get("session_token")
    auth_header = request.headers.get("authorization")
    from .auth import _resolve_session_token
    from ..user_scope import SEED_USER_ID

    token = await _resolve_session_token(cookie_token, auth_header)
    if token:
        from ..database import get_session
        sess = get_session(token)
        if sess and sess.get("user_id"):
            user_id = str(sess["user_id"])
            _bind_copilot_memory(user_id)
            return user_id
    _bind_copilot_memory(SEED_USER_ID)
    return SEED_USER_ID


class ChatMessageModel(BaseModel):
    role: str
    content: str
    timestamp: str
    steps: Optional[List[dict[str, Any]]] = None
    summary: Optional[dict[str, Any]] = None
    previousWorkflow: Optional[dict[str, Any]] = None
    newWorkflow: Optional[dict[str, Any]] = None
    automationLink: Optional[dict[str, Any]] = None
    reverted: Optional[bool] = None


class ChatSessionSaveRequest(BaseModel):
    title: Optional[str] = None
    messages: List[ChatMessageModel]


@router.get("/chats")
async def list_chats(request: Request):
    user_id = await get_user_id(request)
    from ..database import list_chats as db_list_chats
    chats = db_list_chats(user_id)
    return {"chats": chats}


@router.get("/chats/{session_id}")
async def get_chat(session_id: str, request: Request):
    user_id = await get_user_id(request)
    from ..database import get_chat as db_get_chat
    chat = db_get_chat(session_id, user_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return chat


@router.post("/chats/{session_id}")
async def save_chat(session_id: str, req: ChatSessionSaveRequest, request: Request):
    user_id = await get_user_id(request)
    from ..database import save_chat as db_save_chat
    
    messages_dict = [msg.dict() for msg in req.messages]
    
    title = req.title
    if not title and messages_dict:
        first_user_msg = next((m for m in messages_dict if m["role"] == "user"), None)
        if first_user_msg:
            content = first_user_msg["content"]
            title = content[:50] + "..." if len(content) > 50 else content
        else:
            title = "New Chat"
    elif not title:
        title = "New Chat"

    db_save_chat(session_id, user_id, title, messages_dict)
    return {"ok": True}


@router.delete("/chats/{session_id}")
async def delete_chat(session_id: str, request: Request):
    user_id = await get_user_id(request)
    from ..database import delete_chat as db_delete_chat
    db_delete_chat(session_id, user_id)
    return {"ok": True}
