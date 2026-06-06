"""Full-stack Sherpa disposition matrix — mirrors UI /copilot/route pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

DispositionKind = Literal["plan", "answer", "clarify", "any"]
ClarifyExpect = Literal["yes", "no", "any"]


@dataclass(frozen=True)
class DispositionMatrixCase:
    case_id: str
    message: str
    description: str
    has_workflow: bool = False
    has_run_log: bool = False
    workflow_name: str | None = None
    thread_messages: list[dict[str, str]] = field(default_factory=list)
    current_workflow: dict[str, Any] | None = None
    expected_intent: str | None = None
    allowed_intents: frozenset[str] = frozenset()
    expected_disposition: DispositionKind = "any"
    expect_clarify: ClarifyExpect = "any"
    expect_propose_build_plan: bool | None = None
    expect_propose_fix_plan: bool | None = None
    expect_wants_sample_run: bool | None = None
    expect_edit_existing: bool | None = None
    extra_check: Callable[[Any], None] | None = None


_ORDERS_WF = {
    "name": "Orders Top Contributors Excel Report",
    "nodes": [
        {"id": "n01", "type": "manual_trigger", "label": "Start"},
        {"id": "n02", "type": "csv_extract", "label": "Load Orders", "config": {"source": "orders.csv"}},
        {"id": "n03", "type": "group_by", "label": "Aggregate", "config": {"groupBy": "region"}},
        {"id": "n04", "type": "sort", "label": "Rank", "config": {"sortBy": "total_revenue"}},
        {"id": "n05", "type": "excel_output", "label": "Export", "config": {"filename": "Orders_Top_Contributors_Report.xlsx"}},
        {"id": "n08", "type": "agent", "label": "Draft Email for Stakeholders"},
    ],
    "edges": [],
}

_RUN_REVIEW_THREAD = [
    {
        "role": "user",
        "content": (
            'Review the latest run of "Orders Top Contributors Excel Report" '
            "and suggest one change to improve reliability."
        ),
    },
    {
        "role": "assistant",
        "content": (
            "**Orders Top Contributors Excel Report Run Summary**\n"
            "Draft Email for Stakeholders (agent): did not execute.\n\n"
            "**Next step:** Update the workflow to ensure the 'Draft Email for Stakeholders' "
            "node (n08) executes as intended.\n\n"
            "Want me to check the connections to node n08?"
        ),
    },
]

_SAMPLE_RUN_THREAD = [
    {"role": "user", "content": "Build orders excel pipeline"},
    {
        "role": "assistant",
        "content": (
            "I built **Orders Top Contributors Excel Report**.\n\n"
            "**Next step:** Run **Orders Top Contributors Excel Report** with sample data "
            "to preview the export.\n\n"
            "Want me to start a sample run now?"
        ),
    },
]

_EDIT_THREAD = [
    {
        "role": "assistant",
        "content": (
            "**Next step:** Loosen the filter on **Validate Report Content** "
            "in **Orders Top Contributors Excel Report**.\n\n"
            "Want me to apply that change on the canvas?"
        ),
    },
]


def _expect_thinking(route_resp: Any) -> None:
    thinking = (
        (route_resp.disposition.thinking if route_resp.disposition else "")
        or route_resp.thinking_preview
        or (route_resp.metadata.thinking_preview if route_resp.metadata else "")
        or ""
    )
    assert thinking.strip(), "expected thinking_preview or disposition.thinking"


INTENT_DISPOSITION_MATRIX: list[DispositionMatrixCase] = [
    DispositionMatrixCase(
        case_id="01_run_review_by_name",
        message=(
            'Review the latest run of "Orders Top Contributors Excel Report" '
            "and suggest one change to improve reliability."
        ),
        description="Run review by quoted workflow name",
        has_workflow=True,
        has_run_log=True,
        workflow_name="Orders Top Contributors Excel Report",
        current_workflow=_ORDERS_WF,
        allowed_intents=frozenset({"explain_run", "query_run_data"}),
        expected_disposition="answer",
        expect_clarify="no",
        extra_check=_expect_thinking,
    ),
    DispositionMatrixCase(
        case_id="02_show_fix_plan_followup",
        message="ok show the plan",
        description="After run review, show numbered fix plan — not rebuild",
        has_workflow=True,
        workflow_name="Orders Top Contributors Excel Report",
        thread_messages=_RUN_REVIEW_THREAD,
        current_workflow=_ORDERS_WF,
        expected_intent="ask",
        expected_disposition="plan",
        expect_clarify="no",
        expect_propose_fix_plan=True,
        expect_propose_build_plan=True,
        expect_edit_existing=True,
    ),
    DispositionMatrixCase(
        case_id="03_sample_run_yes",
        message="yes",
        description="Affirm sample-run offer",
        has_workflow=True,
        workflow_name="Orders Top Contributors Excel Report",
        thread_messages=_SAMPLE_RUN_THREAD,
        current_workflow=_ORDERS_WF,
        expected_intent="ask",
        expected_disposition="answer",
        expect_clarify="no",
        expect_wants_sample_run=True,
        expect_edit_existing=False,
    ),
    DispositionMatrixCase(
        case_id="04_canvas_edit_yes",
        message="yes",
        description="Affirm canvas edit offer",
        has_workflow=True,
        workflow_name="Orders Top Contributors Excel Report",
        thread_messages=_EDIT_THREAD,
        current_workflow=_ORDERS_WF,
        expected_intent="build",
        expected_disposition="answer",
        expect_clarify="no",
        expect_edit_existing=True,
    ),
    DispositionMatrixCase(
        case_id="05_vague_new_build",
        message="build a report",
        description="Vague new build → plan-first (may clarify if LLM adds questions)",
        has_workflow=False,
        allowed_intents=frozenset({"build", "ask"}),
        expected_disposition="plan",
        expect_clarify="any",
        expect_propose_build_plan=True,
    ),
    DispositionMatrixCase(
        case_id="06_detailed_new_build",
        message=(
            "Load orders.csv, aggregate revenue by region, sort descending, "
            "and export Orders_Top_Contributors_Report.xlsx with an email summary step."
        ),
        description="Detailed new build → plan gate",
        has_workflow=False,
        allowed_intents=frozenset({"build", "ask"}),
        expected_disposition="plan",
        expect_clarify="no",
        expect_propose_build_plan=True,
    ),
    DispositionMatrixCase(
        case_id="07_platform_ask",
        message="What does the filter node do and when should I use it?",
        description="Platform Q&A — answer, no clarify",
        has_workflow=True,
        current_workflow=_ORDERS_WF,
        expected_intent="ask",
        expected_disposition="answer",
        expect_clarify="no",
    ),
    DispositionMatrixCase(
        case_id="08_named_run_sample",
        message='Run "Orders Top Contributors Excel Report" with sample data',
        description="Named workflow sample run",
        has_workflow=False,
        expected_intent="ask",
        expected_disposition="answer",
        expect_clarify="no",
        expect_wants_sample_run=True,
    ),
    DispositionMatrixCase(
        case_id="09_improve_existing_named",
        message=(
            'Improve "Orders Top Contributors Excel Report" by wiring the email agent '
            "after the excel export so it always runs."
        ),
        description="Named edit on existing workflow",
        has_workflow=True,
        current_workflow=_ORDERS_WF,
        allowed_intents=frozenset({"build"}),
        expected_disposition="answer",
        expect_clarify="no",
        expect_edit_existing=True,
    ),
    DispositionMatrixCase(
        case_id="10_automate_schedule",
        message="Schedule Orders Top Contributors Excel Report to run every morning at 8am",
        description="Automation intent",
        has_workflow=True,
        workflow_name="Orders Top Contributors Excel Report",
        current_workflow=_ORDERS_WF,
        expected_intent="automate",
        expected_disposition="answer",
        expect_clarify="no",
    ),
    DispositionMatrixCase(
        case_id="11_load_by_name",
        message='Load "Orders Top Contributors Excel Report" onto the canvas',
        description="Load saved workflow",
        has_workflow=False,
        allowed_intents=frozenset({"load"}),
        expected_disposition="answer",
        expect_clarify="any",
    ),
    DispositionMatrixCase(
        case_id="12_bare_affirmation",
        message="ok",
        description="Bare affirmation without thread — may clarify",
        has_workflow=True,
        current_workflow=_ORDERS_WF,
        expect_clarify="any",
    ),
    DispositionMatrixCase(
        case_id="13_do_it_after_run_review",
        message="do it",
        description="Apply prior run-review next step",
        has_workflow=True,
        thread_messages=_RUN_REVIEW_THREAD,
        current_workflow=_ORDERS_WF,
        allowed_intents=frozenset({"build", "ask"}),
        expected_disposition="answer",
        expect_clarify="no",
        expect_edit_existing=True,
    ),
    DispositionMatrixCase(
        case_id="14_explain_error",
        message="Why did the join node fail on the last run?",
        description="Error diagnosis",
        has_workflow=True,
        has_run_log=True,
        current_workflow=_ORDERS_WF,
        allowed_intents=frozenset({"explain_error", "explain_run"}),
        expected_disposition="answer",
        expect_clarify="no",
    ),
    DispositionMatrixCase(
        case_id="15_row_count_question",
        message="How many rows were in the final export?",
        description="Run output question",
        has_workflow=True,
        has_run_log=True,
        workflow_name="Orders Top Contributors Excel Report",
        current_workflow=_ORDERS_WF,
        allowed_intents=frozenset({"explain_run", "query_run_data"}),
        expected_disposition="answer",
        expect_clarify="no",
    ),
    DispositionMatrixCase(
        case_id="16_create_from_scratch_short",
        message="new pipeline",
        description="Very vague create — plan-first",
        has_workflow=False,
        allowed_intents=frozenset({"build", "ask"}),
        expected_disposition="plan",
        expect_clarify="any",
        expect_propose_build_plan=True,
    ),
    DispositionMatrixCase(
        case_id="17_slash_style_build",
        message="/build Load orders.csv and export excel top contributors",
        description="Slash build command",
        has_workflow=False,
        allowed_intents=frozenset({"build", "ask"}),
        expected_disposition="plan",
        expect_propose_build_plan=True,
    ),
]
