"""Suggestion-style Sherpa router test matrix (live Gemini integration)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class SherpaRouterCase:
    case_id: str
    message: str
    expected_intents: frozenset[str]
    context: dict[str, Any] = field(default_factory=dict)
    check: Callable[[Any], None] | None = None


def _expect_workflow_name(route: Any, needle: str) -> None:
    wf = str((route.metadata or {}).get("workflow_name") or "").lower()
    assert needle.lower() in wf, f"workflow_name should mention {needle!r}, got {wf!r}"


def _expect_enhanced_contains(*needles: str) -> Callable[[Any], None]:
    def _check(route: Any) -> None:
        eq = (route.enhanced_question or "").lower()
        assert eq.strip(), "enhanced_question must not be empty"
        kw = " ".join(route.keywords).lower()
        missing = [n for n in needles if n.lower() not in eq and n.lower() not in kw]
        assert not missing, f"enhanced_question/keywords missing {missing}: {eq[:200]}"

    return _check


def _check_improve_existing(route: Any) -> None:
    _expect_workflow_name(route, "Join Comms")
    assert (route.metadata or {}).get("edit_existing_workflow") is True
    _expect_enhanced_contains("outlook", "validation")(route)


def _check_explain_run_reliability(route: Any) -> None:
    _expect_workflow_name(route, "Join Comms")
    selector = (route.metadata or {}).get("run_selector")
    assert selector in ("latest", "current", None) or "latest" in (route.enhanced_question or "").lower()


def _check_query_sql(route: Any) -> None:
    meta = route.metadata or {}
    assert meta.get("wants_sql") or "select" in (route.enhanced_question or "").lower()


SHERPA_ROUTER_CASES: list[SherpaRouterCase] = [
    SherpaRouterCase(
        case_id="build_csv_export",
        message="Load comms_messages, filter high-risk rows, and export a CSV summary.",
        expected_intents=frozenset({"build"}),
        check=_expect_enhanced_contains("csv", "comms"),
    ),
    SherpaRouterCase(
        case_id="build_excel_report",
        message="Create an Excel report from hs_alerts with sorted top contributors.",
        expected_intents=frozenset({"build"}),
        check=_expect_enhanced_contains("excel"),
    ),
    SherpaRouterCase(
        case_id="build_outlook_digest",
        message="Send a workflow digest email through Outlook when the run completes.",
        expected_intents=frozenset({"build"}),
        check=_expect_enhanced_contains("outlook"),
    ),
    SherpaRouterCase(
        case_id="build_join_pipeline",
        message="Join comms_messages with hs_alerts and produce a ranked output file.",
        expected_intents=frozenset({"build"}),
        check=_expect_enhanced_contains("join"),
    ),
    SherpaRouterCase(
        case_id="build_improve_existing",
        message=(
            'Improve "Join Comms Messages with HS Alerts and Rank" with validation, '
            "a branch for failures, and an Outlook summary when the run completes."
        ),
        expected_intents=frozenset({"build"}),
        context={"recent_run_workflows": ["Join Comms Messages with HS Alerts and Rank"]},
        check=_check_improve_existing,
    ),
    SherpaRouterCase(
        case_id="ask_node_discovery",
        message="Which node types are best for filtering and branching workflow data?",
        expected_intents=frozenset({"ask"}),
    ),
    SherpaRouterCase(
        case_id="ask_data_sources",
        message="What data sources are available, and how should I use comms_messages?",
        expected_intents=frozenset({"ask"}),
    ),
    SherpaRouterCase(
        case_id="load_saved_workflow",
        message='Open the workflow "Join Comms Messages with HS Alerts and Rank" on the canvas.',
        expected_intents=frozenset({"load"}),
        check=lambda r: _expect_workflow_name(r, "Join Comms"),
    ),
    SherpaRouterCase(
        case_id="automate_daily_schedule",
        message=(
            'Create an automation for "Join Comms Messages with HS Alerts and Rank" '
            "to run every weekday at 9:30 AM."
        ),
        expected_intents=frozenset({"automate"}),
        check=lambda r: _expect_workflow_name(r, "Join Comms"),
    ),
    SherpaRouterCase(
        case_id="explain_run_reliability",
        message=(
            'Review the latest run of "Join Comms Messages with HS Alerts and Rank" '
            "and suggest one change to improve reliability."
        ),
        expected_intents=frozenset({"explain_run"}),
        context={"recent_run_workflows": ["Join Comms Messages with HS Alerts and Rank"]},
        check=_check_explain_run_reliability,
    ),
    SherpaRouterCase(
        case_id="explain_run_top_trader",
        message="How many rows were produced and who is the top trader by total relevance?",
        expected_intents=frozenset({"explain_run"}),
        context={"has_run_log": True, "run_workflow_name": "Join Comms Messages with HS Alerts and Rank"},
        check=_expect_enhanced_contains("row", "trader"),
    ),
    SherpaRouterCase(
        case_id="explain_error_join",
        message="Why did the join node fail on my last run?",
        expected_intents=frozenset({"explain_error", "explain_run"}),
        context={
            "has_run_log": True,
            "recent_errors": [{"message": "join node error", "node_id": "n04"}],
        },
    ),
    SherpaRouterCase(
        case_id="query_run_data_sql",
        message=(
            "On the latest Join Comms run, run: "
            "SELECT trader_name, COUNT(*) AS n FROM run_output GROUP BY trader_name ORDER BY n DESC LIMIT 5"
        ),
        expected_intents=frozenset({"query_run_data", "explain_run"}),
        context={"recent_run_workflows": ["Join Comms Messages with HS Alerts and Rank"]},
        check=_check_query_sql,
    ),
]
