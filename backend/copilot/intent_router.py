"""LLM-driven copilot intent routing — delegates to llm_router.SherpaRoute."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from copilot.llm_router import SherpaRoute, route_sherpa_message
from llm import GeminiAdapter


@dataclass(frozen=True)
class CopilotIntentResult:
    intent: str
    reason: str
    source: str  # "llm" | "heuristic"
    enhanced_question: str = ""
    keywords: tuple[str, ...] = ()
    metadata: dict[str, Any] | None = None


def _route_to_result(route: SherpaRoute) -> CopilotIntentResult:
    return CopilotIntentResult(
        intent=route.intent,
        reason=route.reason,
        source=route.source,
        enhanced_question=route.enhanced_question,
        keywords=route.keywords,
        metadata=dict(route.metadata),
    )


def classify_copilot_intent(
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
) -> CopilotIntentResult:
    """Classify user message into structured SherpaRoute (legacy wrapper)."""
    route = route_sherpa_message(
        message,
        has_workflow=has_workflow,
        workflow_name=workflow_name,
        has_run_log=has_run_log,
        run_id=run_id,
        run_workflow_name=run_workflow_name,
        recent_errors=recent_errors,
        thread_context=thread_context,
        recent_run_workflows=recent_run_workflows,
        adapter=adapter,
        canvas_workflow=canvas_workflow,
    )
    return _route_to_result(route)


def route_sherpa(
    message: str,
    **kwargs: Any,
) -> SherpaRoute:
    """Primary entry point — returns full SherpaRoute."""
    return route_sherpa_message(message, **kwargs)
