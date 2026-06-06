"""Pydantic request/response models for the HTTP API.

These classes are intentionally thin: routers own behavior, while these
models describe the wire contract that FastAPI exposes through OpenAPI.
Good field descriptions here help both humans and frontend developers
understand what shape each endpoint expects without reading router code.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RunWorkflowRequest(BaseModel):
    dag: dict[str, Any] = Field(
        ...,
        description=(
            "Workflow DAG JSON with nodes and edges. Nodes must use backend "
            "NodeSpec type_id values and config keys."
        ),
    )
    alert_payload: dict[str, Any] = Field(
        ...,
        description=(
            "Opaque alert/event payload for the run. ALERT_TRIGGER binds known "
            "keys into RunContext values for downstream query templates."
        ),
    )


class ValidateWorkflowRequest(BaseModel):
    dag: dict[str, Any] = Field(
        ...,
        description="Workflow DAG JSON to validate without executing any node handlers.",
    )


class WorkflowYamlParseRequest(BaseModel):
    content: str = Field(
        ...,
        description="Human-authored workflow YAML to parse into the runtime JSON DAG shape.",
    )


class WorkflowYamlRenderRequest(BaseModel):
    workflow: dict[str, Any] = Field(
        ...,
        description="Runtime workflow DAG JSON to render as human-readable YAML.",
    )


class CopilotChatRequest(BaseModel):
    message: str = Field(..., description="Free-form user message for the copilot chat endpoint.")
    reset_history: bool = Field(
        False,
        description="When true, clear this session's server-side chat history before sending.",
    )
    session_id: Optional[str] = Field(
        None,
        description=(
            "Optional caller-owned session id for multi-turn chat. Omit for a "
            "stateless single-turn call."
        ),
    )
    current_workflow: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional canvas workflow for contextual Q&A about the loaded DAG.",
    )
    recent_errors: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Optional validator/runtime errors for troubleshooting answers.",
    )
    propose_build_plan: bool = Field(
        False,
        description="When true, reply is plan-only with a create-on-canvas confirm footer.",
    )


class CopilotThreadMessage(BaseModel):
    role: str = Field(..., description='"user" or "assistant".')
    content: str = Field(..., description="Message body (prior turns only; current turn is separate).")


class CopilotClassifyRequest(BaseModel):
    message: str = Field(..., description="User message to classify for build vs ask routing.")
    has_workflow: bool = Field(
        False,
        description="True when a workflow is loaded on the canvas.",
    )
    has_run_log: bool = Field(
        False,
        description="True when a completed run is available in the output panel.",
    )
    workflow_name: Optional[str] = Field(
        None,
        description="Display name of the workflow on canvas.",
    )
    run_id: Optional[str] = Field(
        None,
        description="Run id of the in-memory completed run, if any.",
    )
    run_workflow_name: Optional[str] = Field(
        None,
        description="Workflow name associated with the in-memory run.",
    )
    recent_errors: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Optional validator/runtime errors for intent context.",
    )
    session_id: Optional[str] = Field(
        None,
        description="Copilot chat session id for thread-scoped routing context.",
    )
    thread_messages: Optional[List[CopilotThreadMessage]] = Field(
        None,
        description="Prior turns in this session (excluding the current message).",
    )
    current_workflow: Optional[Dict[str, Any]] = Field(
        None,
        description="Workflow JSON currently loaded on the canvas.",
    )


class CopilotResolveContextRequest(BaseModel):
    route_metadata: Dict[str, Any] = Field(default_factory=dict)
    current_workflow: Optional[Dict[str, Any]] = None
    run_log: list[dict[str, Any]] = Field(default_factory=list)
    run_result: Optional[Dict[str, Any]] = None
    run_error: Optional[str] = None


class CopilotRouteMetadata(BaseModel):
    workflow_name: Optional[str] = None
    run_selector: Optional[str] = None
    run_id: Optional[str] = None
    run_status_filter: Optional[str] = None
    error_message: Optional[str] = None
    node_id: Optional[str] = None
    topics: List[str] = Field(default_factory=list)
    wants_sql: bool = False
    edit_existing_workflow: bool = False
    wants_sample_run: bool = False
    slash_route: Optional[str] = Field(
        None,
        description="When set, the user forced routing via /slash (e.g. run, build, check-run).",
    )
    suggested_sql: Optional[str] = Field(
        None,
        description="Approximate SELECT against run_output for downstream verification.",
    )
    verification_plan: Optional[List[str]] = Field(
        None,
        description="Deterministic verification checks: row_counts, join_orphans, etc.",
    )
    clarification_resolved: bool = Field(
        False,
        description="Set after the user answers a Sherpa clarification prompt.",
    )
    propose_build_plan: bool = Field(
        False,
        description="When true, ask/chat should output a plan only — not create on canvas yet.",
    )
    build_plan_confirmed: bool = Field(
        False,
        description="User confirmed the plan; harness may create on canvas.",
    )
    original_user_request: Optional[str] = Field(
        None,
        description="Original user message before plan/confirm steps.",
    )
    awaiting_plan_revision: bool = Field(
        False,
        description="User rejected a plan; next ask turn revises before re-confirm.",
    )
    plan_revision_reason: Optional[str] = Field(
        None,
        description="User-provided reason when rejecting a build plan.",
    )
    sherpa_disposition: Optional[str] = Field(
        None,
        description="Intent layer output: plan | answer | clarify.",
    )
    disposition_confidence: Optional[float] = Field(
        None,
        description="0-1 confidence from the intent understanding layer.",
    )
    thinking_preview: Optional[str] = Field(
        None,
        description="2-4 line thinking monologue shown before execution.",
    )
    propose_fix_plan: bool = Field(
        False,
        description="Numbered fix plan after run review — not a new workflow build.",
    )


class SherpaDispositionPayload(BaseModel):
    kind: str = Field("", description="plan | answer | clarify")
    thinking: str = ""
    confidence: float = 1.0
    reason: str = ""


class SherpaClarificationOption(BaseModel):
    id: str = Field(..., description='yes | no | other | a | b | c | …')
    label: str = ""
    description: str = ""


class SherpaClarificationQuestionPayload(BaseModel):
    id: str = "q1"
    kind: str = Field("choice", description="confirm | choice")
    question: str = ""
    options: List[SherpaClarificationOption] = Field(default_factory=list)
    default_option_id: Optional[str] = None
    allow_multiple: bool = False


class SherpaClarificationAnswerItem(BaseModel):
    question_id: Optional[str] = None
    question: str = ""
    kind: str = "choice"
    selection_ids: List[str] = Field(default_factory=list)
    other_text: Optional[str] = None
    selection_labels: List[str] = Field(default_factory=list)


class SherpaClarificationPayload(BaseModel):
    needed: bool = False
    kind: Optional[str] = Field(None, description="confirm | choice when needed is true.")
    question: str = ""
    options: List[SherpaClarificationOption] = Field(default_factory=list)
    default_option_id: Optional[str] = None
    questions: List[SherpaClarificationQuestionPayload] = Field(default_factory=list)
    reason: str = ""


class CopilotClassifyResponse(BaseModel):
    intent: str = Field(
        ...,
        description='build | ask | automate | load | explain_run | explain_error | query_run_data',
    )
    reason: str = Field("", description="Short explanation of the routing decision.")
    source: str = Field("", description='"llm" or "heuristic".')
    enhanced_question: str = Field("", description="Normalized question for downstream handlers.")
    keywords: List[str] = Field(default_factory=list)
    metadata: CopilotRouteMetadata = Field(default_factory=CopilotRouteMetadata)
    clarification: Optional[SherpaClarificationPayload] = Field(
        None,
        description="When set with needed=true, UI must collect an answer before executing the route.",
    )
    disposition: Optional[SherpaDispositionPayload] = Field(
        None,
        description="Unified intent layer: what Sherpa will do next (plan, answer, or clarify).",
    )
    thinking_preview: Optional[str] = Field(
        None,
        description="Thinking monologue from intent layer, shown before streaming begins.",
    )


class CopilotClarifyResolveRequest(BaseModel):
    message: str = Field(..., description="Original user message that triggered routing.")
    selection_id: str = Field(
        "",
        description="Legacy single-select id (yes, no, other, a, b, …). Prefer answers[].",
    )
    other_text: Optional[str] = Field(None, description="Free text when selection_id is other.")
    answers: Optional[List[SherpaClarificationAnswerItem]] = Field(
        None,
        description="One or more Questions-panel answers (multi-question / multi-select).",
    )
    clarification_kind: str = Field("confirm", description="confirm | choice from prior clarification.")
    clarification_question: Optional[str] = Field(
        None,
        description="Question text shown in the Questions panel (stored on the resolved route).",
    )
    selection_label: Optional[str] = Field(None, description="Human label for the selected option.")
    selection_description: Optional[str] = Field(
        None,
        description="Helper text for the selected option.",
    )
    pending_route: Dict[str, Any] = Field(
        ...,
        description="Route snapshot from /copilot/route before clarification.",
    )
    has_workflow: bool = False
    session_id: Optional[str] = None
    thread_messages: Optional[List[CopilotThreadMessage]] = None
    current_workflow: Optional[Dict[str, Any]] = None


class RunLogQueryRequest(BaseModel):
    sql: str = Field(..., description="SELECT-only SQL against table run_output.")


class CopilotAutomateRequest(BaseModel):
    message: str = Field(..., description="Natural-language automation request.")
    current_workflow: Optional[Dict[str, Any]] = Field(
        None,
        description="Workflow currently loaded on the canvas.",
    )
    critic_iterations: int = Field(
        2,
        description="Max harness repair attempts when a workflow must be built first.",
    )
    session_id: Optional[str] = Field(
        None,
        description="Copilot chat session id for thread-scoped automation context.",
    )
    thread_messages: Optional[List[CopilotThreadMessage]] = Field(
        None,
        description="Prior turns in this session (excluding the current message).",
    )


class CopilotLoadRequest(BaseModel):
    message: str = Field(..., description="Natural-language request to load a saved workflow.")
    session_id: Optional[str] = Field(
        None,
        description="Copilot chat session id for thread context.",
    )
    thread_messages: Optional[List[CopilotThreadMessage]] = Field(
        None,
        description="Prior turns in this session (excluding the current message).",
    )


class CopilotGenerateRequest(BaseModel):
    prompt: str = Field(
        ...,
        description="Scenario or edit instruction used by the agent harness to draft or repair a workflow.",
    )
    critic_iterations: int = Field(
        2,
        description=(
            "Maximum LLM repair attempts after deterministic validation failures. "
            "Default is 2 for better first-pass reliability with low added latency."
        ),
    )
    # Optional editing context. When the user is iterating on an
    # existing workflow (fixing errors, adding nodes, renaming things)
    # the frontend attaches the current canvas state + any recent
    # failures so the planner can produce a targeted edit rather than
    # a greenfield draft. Both fields default to None so the legacy
    # "describe a scenario → generate from scratch" path is unchanged.
    current_workflow: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Existing canvas workflow for edit-mode generation. When omitted, "
            "the planner creates a new workflow from scratch."
        ),
    )
    recent_errors: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Recent validator/runtime errors to help the planner produce a targeted fix.",
    )
    # When the user has a node selected on the canvas and writes
    # something deictic ("remove this", "change this threshold") we
    # ship the selected node id so the LLM can resolve the referent
    # instead of guessing.
    selected_node_id: Optional[str] = Field(
        None,
        description=(
            "Canvas node id the user currently selected, used to resolve instructions "
            "like 'change this threshold'."
        ),
    )
    compiler_mode: Optional[str] = Field(
        "harness",
        description=(
            "Generation mode hint. Runtime uses AgentRunner "
            "(classify → retrieve → generate → validate → auto-fix → repair → smoke)."
        ),
    )
    session_id: Optional[str] = Field(
        None,
        description="Copilot chat session id for thread-scoped generation context.",
    )
    thread_messages: Optional[List[CopilotThreadMessage]] = Field(
        None,
        description="Prior turns in this session (excluding the current message).",
    )


class CopilotExplainRunRequest(BaseModel):
    workflow: dict[str, Any] = Field(..., description="Workflow DAG that was executed.")
    run_log: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Per-node run log entries captured from /run/stream.",
    )
    run_result: Optional[dict[str, Any]] = Field(
        None,
        description="Optional workflow_complete result payload from the run stream.",
    )
    run_error: Optional[str] = Field(
        None,
        description="Optional terminal run error string when workflow ended in error.",
    )
    user_message: Optional[str] = Field(
        None,
        description="Optional user follow-up steering the run analysis (e.g. top traders).",
    )
    suggested_sql: Optional[str] = Field(
        None,
        description="Approximate verification SQL from the router (SELECT on run_output).",
    )
    route_metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Full router metadata (verification_plan, wants_sql, etc.).",
    )
