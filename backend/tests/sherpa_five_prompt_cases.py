"""Five Sherpa prompt types for live Gemini parity checks (thinking + Next step)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SherpaFivePromptCase:
    case_id: str
    route_type: str
    message: str
    expected_intent: str
    context: dict[str, Any] = field(default_factory=dict)
    description: str = ""


SHERPA_FIVE_PROMPT_CASES: tuple[SherpaFivePromptCase, ...] = (
    SherpaFivePromptCase(
        case_id="build_excel_orders",
        route_type="build",
        message="Create an Excel report from orders.csv with sorted top contributors.",
        expected_intent="build",
        description="Greenfield build — Excel export pipeline",
    ),
    SherpaFivePromptCase(
        case_id="ask_node_filtering",
        route_type="ask",
        message="Which node types are best for filtering and branching workflow data?",
        expected_intent="ask",
        description="Platform Q&A — no canvas mutation",
    ),
    SherpaFivePromptCase(
        case_id="explain_run_reliability",
        route_type="explain_run",
        message=(
            'Review the latest run of "Join Comms Messages with HS Alerts and Rank" '
            "and suggest one change to improve reliability."
        ),
        expected_intent="explain_run",
        context={"recent_run_workflows": ["Join Comms Messages with HS Alerts and Rank"]},
        description="Post-run review with Next step fix offer",
    ),
    SherpaFivePromptCase(
        case_id="load_saved_workflow",
        route_type="load",
        message='Open the workflow "Join Comms Messages with HS Alerts and Rank" on the canvas.',
        expected_intent="load",
        description="Load saved workflow from library",
    ),
    SherpaFivePromptCase(
        case_id="automate_weekday_schedule",
        route_type="automate",
        message=(
            'Create an automation for "Join Comms Messages with HS Alerts and Rank" '
            "to run every weekday at 9:30 AM."
        ),
        expected_intent="automate",
        context={"recent_run_workflows": ["Join Comms Messages with HS Alerts and Rank"]},
        description="Schedule automation on existing workflow",
    ),
)
