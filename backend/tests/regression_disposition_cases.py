"""Extended regression matrix — difficult prompts, sequences, guardrails, integrations."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from tests.intent_disposition_matrix_cases import (
    DispositionMatrixCase,
    _ORDERS_WF,
    _RUN_REVIEW_THREAD,
)

ClarifyExpect = Literal["yes", "no", "any"]
DispositionKind = Literal["plan", "answer", "clarify", "any"]


@dataclass(frozen=True)
class RegressionCase(DispositionMatrixCase):
    """DispositionMatrixCase plus regression tags for reporting."""
    tags: frozenset[str] = frozenset()


_RUN_REVIEW_THEN_PLAN = _RUN_REVIEW_THREAD + [
    {"role": "user", "content": "ok show the plan"},
    {
        "role": "assistant",
        "content": (
            "Below is the plan.\n"
            "1. Wire n08 after the excel export.\n"
            "2. Set agent config to always run.\n"
            "3. Re-run with sample data.\n\n"
            "Approve this fix plan to apply on the canvas?"
        ),
    },
]

_BUILD_PLAN_THREAD = [
    {"role": "user", "content": "build a report"},
    {
        "role": "assistant",
        "content": (
            "Below is the plan.\n"
            "1. Load orders.csv\n"
            "2. Aggregate by region\n"
            "3. Export excel\n\n"
            "Should I create **Orders Report** on the canvas now?"
        ),
    },
]


def _expect_workflow_not_found_clarify(resp: Any) -> None:
    clar = resp.clarification
    assert clar and clar.needed, "expected workflow-not-found clarification"
    q = (clar.questions or [{}])[0]
    text = (q.question or "").lower()
    assert "not found" in text or "what would you like" in text, f"unexpected clarify question: {q.question}"


REGRESSION_DISPOSITION_CASES: list[RegressionCase] = [
    # ── Missing workflows ──
    RegressionCase(
        case_id="R01_load_phantom",
        message='Load "Ghost Workflow XYZ 99999" onto the canvas',
        description="Load workflow that does not exist",
        tags=frozenset({"missing_workflow", "load"}),
        has_workflow=False,
        allowed_intents=frozenset({"load"}),
        expected_disposition="answer",
        expect_clarify="any",
    ),
    RegressionCase(
        case_id="R02_run_phantom_sample",
        message='Run "Ghost Alert Digest" with sample data',
        description="Named sample run for missing workflow",
        tags=frozenset({"missing_workflow", "sample_run"}),
        has_workflow=False,
        expected_intent="ask",
        expected_disposition="answer",
        expect_clarify="no",
        expect_wants_sample_run=True,
    ),
    RegressionCase(
        case_id="R03_review_phantom_run",
        message='Review the latest run of "Nonexistent KPI Dashboard" and suggest one fix',
        description="Run review for workflow not on canvas",
        tags=frozenset({"missing_workflow", "run_review"}),
        has_workflow=False,
        allowed_intents=frozenset({"explain_run", "query_run_data", "ask"}),
        expected_disposition="answer",
        expect_clarify="yes",
        extra_check=_expect_workflow_not_found_clarify,
    ),
    RegressionCase(
        case_id="R04_improve_phantom",
        message='Improve "Ghost Workflow XYZ 99999" by adding a validation step',
        description="Named edit for missing workflow — plan-first or clarify",
        tags=frozenset({"missing_workflow", "edit"}),
        has_workflow=False,
        allowed_intents=frozenset({"build", "ask"}),
        expected_disposition="plan",
        expect_clarify="any",
        expect_propose_build_plan=True,
    ),
    # ── Existing workflows ──
    RegressionCase(
        case_id="R05_load_orders_exists",
        message='Load "Orders Top Contributors Excel Report" onto the canvas',
        description="Load workflow that exists in library",
        tags=frozenset({"existing_workflow", "load"}),
        has_workflow=False,
        allowed_intents=frozenset({"load"}),
        expected_disposition="answer",
        expect_clarify="any",
    ),
    RegressionCase(
        case_id="R06_edit_orders_on_canvas",
        message=(
            'Improve "Orders Top Contributors Excel Report" by wiring the email agent '
            "after the excel export so it always runs."
        ),
        description="Edit existing workflow on canvas",
        tags=frozenset({"existing_workflow", "edit"}),
        has_workflow=True,
        current_workflow=_ORDERS_WF,
        allowed_intents=frozenset({"build"}),
        expected_disposition="answer",
        expect_clarify="no",
        expect_edit_existing=True,
    ),
    RegressionCase(
        case_id="R07_delta_edit_canvas",
        message="also add a row count check before the excel export",
        description="Delta edit on canvas without quoted name",
        tags=frozenset({"existing_workflow", "edit", "delta"}),
        has_workflow=True,
        current_workflow=_ORDERS_WF,
        allowed_intents=frozenset({"build", "ask"}),
        expected_disposition="answer",
        expect_clarify="any",
        expect_edit_existing=True,
    ),
    # ── GitHub + Confluence builds ──
    RegressionCase(
        case_id="R08_github_confluence_build",
        message=(
            "Use github_mcp to list recent commits, summarize activity with an agent node, "
            "and publish a briefing to Confluence via confluence_mcp."
        ),
        description="GitHub → agent → Confluence new build",
        tags=frozenset({"integration", "github", "confluence", "new_build"}),
        has_workflow=False,
        allowed_intents=frozenset({"build", "ask"}),
        expected_disposition="plan",
        expect_clarify="no",
        expect_propose_build_plan=True,
    ),
    RegressionCase(
        case_id="R09_confluence_search_build",
        message=(
            "Search Confluence for pages about Q4 revenue, extract action items, "
            "and create Jira issues for each."
        ),
        description="Confluence search + Jira pipeline",
        tags=frozenset({"integration", "confluence", "jira", "new_build"}),
        has_workflow=False,
        allowed_intents=frozenset({"build", "ask"}),
        expected_disposition="plan",
        expect_propose_build_plan=True,
    ),
    RegressionCase(
        case_id="R10_slash_improve_github",
        message="/improve Add github_list_commits before the agent summary step",
        description="Slash improve on canvas workflow",
        tags=frozenset({"integration", "github", "slash", "edit"}),
        has_workflow=True,
        current_workflow=_ORDERS_WF,
        allowed_intents=frozenset({"build"}),
        expected_disposition="answer",
        expect_edit_existing=True,
    ),
    # ── Off-topic / guardrails ──
    RegressionCase(
        case_id="R11_offtopic_weather",
        message="What's the weather in Paris tomorrow?",
        description="Off-topic — should answer politely, not build",
        tags=frozenset({"guardrail", "off_topic"}),
        has_workflow=False,
        expected_intent="ask",
        expected_disposition="answer",
        expect_clarify="no",
        expect_propose_build_plan=False,
    ),
    RegressionCase(
        case_id="R12_offtopic_poem",
        message="Write me a haiku about database migrations",
        description="Creative off-topic — ask route, no plan gate",
        tags=frozenset({"guardrail", "off_topic"}),
        has_workflow=True,
        current_workflow=_ORDERS_WF,
        expected_intent="ask",
        expected_disposition="answer",
        expect_clarify="no",
        expect_propose_build_plan=False,
    ),
    RegressionCase(
        case_id="R13_platform_capabilities",
        message="Which MCP integrations are available for GitHub and Confluence?",
        description="Platform Q&A about integrations",
        tags=frozenset({"guardrail", "platform_qa", "github", "confluence"}),
        has_workflow=False,
        expected_intent="ask",
        expected_disposition="answer",
        expect_clarify="no",
    ),
    RegressionCase(
        case_id="R18_export_how_to_starter",
        message="How do I export workflow results to CSV or Excel?",
        description="Discovery starter prompt — answer directly, never clarify",
        tags=frozenset({"guardrail", "platform_qa", "starter_prompt"}),
        has_workflow=False,
        expected_intent="ask",
        expected_disposition="answer",
        expect_clarify="no",
    ),
    # ── Difficult sequences ──
    RegressionCase(
        case_id="R14_sequence_run_review_plan",
        message="yes approve",
        description="After fix-plan offer in thread — edit existing",
        tags=frozenset({"sequence", "run_review", "plan"}),
        has_workflow=True,
        thread_messages=_RUN_REVIEW_THEN_PLAN,
        current_workflow=_ORDERS_WF,
        allowed_intents=frozenset({"build", "ask"}),
        expected_disposition="answer",
        expect_clarify="any",
        expect_edit_existing=True,
    ),
    RegressionCase(
        case_id="R15_sequence_plan_confirm",
        message="yes create it",
        description="Confirm build plan from prior thread",
        tags=frozenset({"sequence", "new_build", "plan"}),
        has_workflow=False,
        thread_messages=_BUILD_PLAN_THREAD,
        allowed_intents=frozenset({"build", "ask"}),
        expect_clarify="any",
    ),
    RegressionCase(
        case_id="R16_sequence_vague_then_detail",
        message="orders.csv, group by region, excel export, email summary",
        description="Follow-up detail after vague build (simulated thread)",
        tags=frozenset({"sequence", "new_build"}),
        has_workflow=False,
        thread_messages=[
            {"role": "user", "content": "build something"},
            {"role": "assistant", "content": "What data source and output format do you need?"},
        ],
        allowed_intents=frozenset({"build", "ask"}),
        expected_disposition="plan",
        expect_propose_build_plan=True,
    ),
    RegressionCase(
        case_id="R17_contradictory_run_and_build",
        message='Review "Orders Top Contributors Excel Report" run AND rebuild it from scratch as a CSV pipeline',
        description="Mixed run review + new build in one message",
        tags=frozenset({"sequence", "ambiguous"}),
        has_workflow=True,
        has_run_log=True,
        workflow_name="Orders Top Contributors Excel Report",
        current_workflow=_ORDERS_WF,
        allowed_intents=frozenset({"explain_run", "query_run_data", "build", "ask"}),
        expected_disposition="answer",
        expect_clarify="any",
    ),
    RegressionCase(
        case_id="R18_sql_injection_style",
        message="'; DROP TABLE orders; -- now build a report",
        description="Adversarial input — should plan/build safely, not crash",
        tags=frozenset({"guardrail", "adversarial"}),
        has_workflow=False,
        allowed_intents=frozenset({"build", "ask"}),
        expect_clarify="any",
    ),
    RegressionCase(
        case_id="R19_empty_quoted_name",
        message='Load "" onto the canvas',
        description="Malformed quoted name",
        tags=frozenset({"edge_case", "load"}),
        has_workflow=False,
        allowed_intents=frozenset({"load", "ask", "build"}),
        expect_clarify="any",
    ),
    RegressionCase(
        case_id="R20_double_slash_command",
        message="/build /run Load orders and run sample",
        description="Chained slash commands",
        tags=frozenset({"edge_case", "slash"}),
        has_workflow=False,
        allowed_intents=frozenset({"build", "ask", "load"}),
        expect_clarify="any",
    ),
]
