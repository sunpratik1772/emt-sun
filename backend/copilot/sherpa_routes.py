"""Optional Sherpa slash routes — explicit /build, /run, /check-run, etc.

Users can prefix messages with a route (e.g. `/run` or `/improve fix the join`).
Studio also surfaces contextual route chips after builds and runs.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_SLASH_PREFIX_RE = re.compile(r"^/([a-z][a-z0-9-]*)\s*(.*)$", re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class SherpaSlashRoute:
    id: str
    slash: str
    label: str
    description: str
    intent: str
    example: str
    contexts: tuple[str, ...] = ("always",)
    metadata_defaults: dict[str, Any] = field(default_factory=dict)
    default_body: str = ""

    @property
    def command(self) -> str:
        return f"/{self.slash}"

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "slash": self.slash,
            "command": self.command,
            "label": self.label,
            "description": self.description,
            "intent": self.intent,
            "example": self.example,
            "contexts": list(self.contexts),
            "default_body": self.default_body,
        }

    def matches_context(
        self,
        *,
        has_workflow: bool = False,
        has_run_log: bool = False,
        has_errors: bool = False,
    ) -> bool:
        ctx = {
            "always": True,
            "has_workflow": has_workflow,
            "has_run_log": has_run_log,
            "has_errors": has_errors,
            "after_run": has_run_log,
            "after_build": has_workflow and not has_run_log,
        }
        return any(ctx.get(c) for c in self.contexts)


def _wf_name(canvas_workflow: dict[str, Any] | None) -> str:
    if canvas_workflow:
        name = str(canvas_workflow.get("name") or "").strip()
        if name:
            return name
    return "the workflow on canvas"


SHERPA_SLASH_ROUTES: tuple[SherpaSlashRoute, ...] = (
    SherpaSlashRoute(
        id="build",
        slash="build",
        label="Build",
        description="Create or replace a pipeline from your description",
        intent="build",
        example="/build Load comms_messages, filter by keyword, export CSV",
        contexts=("always",),
        default_body="",
    ),
    SherpaSlashRoute(
        id="ask",
        slash="ask",
        label="Ask",
        description="Platform Q&A — nodes, skills, data sources (no run analysis)",
        intent="ask",
        example="/ask What node types can write to Outlook?",
        contexts=("always",),
        default_body="",
    ),
    SherpaSlashRoute(
        id="run",
        slash="run",
        label="Run",
        description="Execute the canvas workflow with sample data",
        intent="ask",
        example="/run",
        contexts=("has_workflow", "after_build", "after_run"),
        metadata_defaults={"wants_sample_run": True, "edit_existing_workflow": False},
        default_body="",
    ),
    SherpaSlashRoute(
        id="check-run",
        slash="check-run",
        label="Check run",
        description="Analyze the current or latest run — row counts, output quality",
        intent="explain_run",
        example="/check-run Summarize row counts and flag anything unexpected",
        contexts=("has_run_log", "after_run"),
        metadata_defaults={"run_selector": "current"},
        default_body="Summarize this run — row counts per node, key output columns, and anything that looks wrong.",
    ),
    SherpaSlashRoute(
        id="follow-up",
        slash="follow-up",
        label="Follow up",
        description="Continue the thread — edits, clarifications, or answers to Sherpa's last step",
        intent="build",
        example="/follow-up Use keyword breach in display_post instead of some_keyword",
        contexts=("has_workflow", "after_build", "after_run"),
        metadata_defaults={"edit_existing_workflow": True},
        default_body="",
    ),
    SherpaSlashRoute(
        id="improve",
        slash="improve",
        label="Improve workflow",
        description="Edit the canvas workflow — reliability, filters, exports",
        intent="build",
        example="/improve Add validation before the CSV export",
        contexts=("has_workflow", "after_build", "after_run"),
        metadata_defaults={"edit_existing_workflow": True},
        default_body="Suggest and apply one concrete improvement to this workflow on the canvas.",
    ),
    SherpaSlashRoute(
        id="fix",
        slash="fix",
        label="Fix",
        description="Repair validation or runtime errors on the canvas workflow",
        intent="build",
        example="/fix Resolve the join type mismatch on the join node",
        contexts=("has_workflow", "has_errors"),
        metadata_defaults={"edit_existing_workflow": True},
        default_body="Fix the top validation or runtime issue on the canvas workflow.",
    ),
    SherpaSlashRoute(
        id="automate",
        slash="automate",
        label="Automate",
        description="Schedule the workflow — cron, daily runs, test automation",
        intent="automate",
        example="/automate Run every weekday at 9am",
        contexts=("has_workflow", "after_build"),
        default_body="",
    ),
    SherpaSlashRoute(
        id="load",
        slash="load",
        label="Load",
        description="Open a saved workflow by name onto the canvas",
        intent="load",
        example="/load Orders export pipeline",
        contexts=("always",),
        default_body="",
    ),
)

_SLASH_BY_NAME: dict[str, SherpaSlashRoute] = {r.slash: r for r in SHERPA_SLASH_ROUTES}
# Aliases
_SLASH_BY_NAME["check"] = _SLASH_BY_NAME["check-run"]
_SLASH_BY_NAME["automation"] = _SLASH_BY_NAME["automate"]


def parse_slash_route(message: str) -> tuple[SherpaSlashRoute | None, str]:
    """Return (route, body) when message starts with /slash; else (None, original)."""
    text = (message or "").strip()
    if not text.startswith("/"):
        return None, text
    match = _SLASH_PREFIX_RE.match(text)
    if not match:
        return None, text
    slug = match.group(1).lower()
    body = (match.group(2) or "").strip()
    route = _SLASH_BY_NAME.get(slug)
    if not route:
        return None, text
    return route, body


def slash_route_to_sherpa_route(
    route: SherpaSlashRoute,
    body: str,
    *,
    fallback_message: str,
    canvas_workflow: dict[str, Any] | None = None,
):
    """Map a slash route + optional body to a SherpaRoute (skips LLM classify)."""
    from copilot.llm_router import SherpaRoute

    wf = _wf_name(canvas_workflow)
    enhanced = body.strip() or route.default_body.strip() or fallback_message
    meta: dict[str, Any] = {
        **route.metadata_defaults,
        "slash_route": route.slash,
    }
    if route.metadata_defaults.get("edit_existing_workflow") and canvas_workflow:
        meta["workflow_name"] = str(canvas_workflow.get("name") or "").strip() or None
    if route.id == "improve" and not body.strip():
        enhanced = (
            f"Suggest and apply one concrete improvement to **{wf}** on the canvas "
            f"(reliability, filters, or export)."
        )
    if route.id == "check-run" and not body.strip():
        enhanced = route.default_body or f"Summarize the latest run of **{wf}**."
    if route.id == "run":
        meta["wants_sample_run"] = True
        meta["edit_existing_workflow"] = False
        if wf and wf != "the workflow on canvas":
            meta["workflow_name"] = wf
        if not enhanced or enhanced == fallback_message:
            enhanced = f"Run **{wf}** with sample data."
    return SherpaRoute(
        intent=route.intent,
        reason=f"Explicit slash route /{route.slash}",
        enhanced_question=enhanced,
        keywords=(route.slash,),
        metadata=meta,
        source="slash_route",
    )


def route_message_with_slash(
    message: str,
    *,
    canvas_workflow: dict[str, Any] | None = None,
):
    """If message uses a known slash route, return the forced SherpaRoute."""
    slash, body = parse_slash_route(message)
    if not slash:
        return None
    return slash_route_to_sherpa_route(
        slash,
        body,
        fallback_message=message,
        canvas_workflow=canvas_workflow,
    )


def list_sherpa_routes(
    *,
    has_workflow: bool = False,
    has_run_log: bool = False,
    has_errors: bool = False,
) -> dict[str, Any]:
    """Catalog + ids to highlight as chips in the copilot UI."""
    routes = [r.to_public_dict() for r in SHERPA_SLASH_ROUTES]
    suggested = [
        r.id
        for r in SHERPA_SLASH_ROUTES
        if r.matches_context(
            has_workflow=has_workflow,
            has_run_log=has_run_log,
            has_errors=has_errors,
        )
    ]
    # Prefer actionable order after a run
    if has_run_log:
        priority = ("check-run", "improve", "run", "follow-up", "fix", "automate", "build", "ask", "load")
    elif has_workflow:
        priority = ("run", "improve", "follow-up", "automate", "build", "check-run", "fix", "ask", "load")
    else:
        priority = ("build", "load", "ask", "run", "automate")
    order = {rid: i for i, rid in enumerate(priority)}
    suggested.sort(key=lambda rid: order.get(rid, 99))
    return {"routes": routes, "suggested_ids": suggested}
