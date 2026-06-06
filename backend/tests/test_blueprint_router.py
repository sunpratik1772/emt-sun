from __future__ import annotations

from generation.harness.blueprint_router import render_blueprint_hint, select_blueprint
from generation.harness.intent import classify


from connectors import get_registry


def _intent_for(text: str):
    return classify(text, known_datasets={s.id for s in get_registry().all()})


def test_market_ticks_confluence_blueprint_selected() -> None:
    scenario = "Use db_query to monitor market_ticks for spread_pips > 100 and publish alert to Confluence"
    decision = select_blueprint(scenario, _intent_for(scenario))
    assert decision is not None
    assert decision.blueprint_id == "market_ticks_spread_monitor"
    assert len(decision.parallel_tasks) >= 2


def test_confluence_jira_blueprint_selected() -> None:
    scenario = "Search Confluence action items and create Jira issues backlog"
    decision = select_blueprint(scenario, _intent_for(scenario))
    assert decision is not None
    assert decision.blueprint_id == "confluence_actions_to_jira"


def test_blueprint_hint_contains_wrapped_context() -> None:
    scenario = "Join hs_alerts with market_ticks and publish to confluence plus jira"
    decision = select_blueprint(scenario, _intent_for(scenario))
    assert decision is not None
    hint = render_blueprint_hint(decision)
    assert "<recommended_blueprint>" in hint
    assert decision.blueprint_id in hint


def test_hs_alerts_market_ticks_excel_picks_join_blueprint() -> None:
    scenario = (
        "Extract data from hs_alerts and market_ticks, join on alert_id, "
        "output to Excel AlertsMarketData.xlsx"
    )
    decision = select_blueprint(scenario, _intent_for(scenario))
    assert decision is not None
    assert decision.blueprint_id == "excel_hs_alerts_market_ticks"
    hint = render_blueprint_hint(decision)
    assert "excel_output" in hint


def test_leads_csv_excel_picks_single_bundle_blueprint() -> None:
    scenario = "Export leads.csv to an Excel spreadsheet"
    decision = select_blueprint(scenario, _intent_for(scenario))
    assert decision is not None
    assert decision.blueprint_id == "excel_leads_csv"
    compact = decision.compact_workflow()
    assert any(n["type"] == "excel_output" for n in compact["nodes"])


def test_hs_alerts_market_ticks_publish_picks_join_blueprint() -> None:
    scenario = "Join hs_alerts with market_ticks and publish to confluence plus jira"
    decision = select_blueprint(scenario, _intent_for(scenario))
    assert decision is not None
    assert decision.blueprint_id == "alerts_ticks_join_publish"


def test_join_followup_with_spread_filter_does_not_pick_spread_monitor() -> None:
    scenario = (
        "On the hs_alerts and market_ticks join, keep only rows where spread_pips >= 80 "
        "and sort by spread descending"
    )
    decision = select_blueprint(scenario, _intent_for(scenario))
    assert decision is None or decision.blueprint_id != "market_ticks_spread_monitor"


def test_ambiguous_followup_without_datasets_does_not_pick_spread_monitor() -> None:
    scenario = (
        "Also make sure the join keeps only rows where spread_pips >= 80 "
        "and sort by spread descending"
    )
    decision = select_blueprint(scenario, _intent_for(scenario))
    assert decision is None


def test_blueprint_demo_files_exist() -> None:
    scenario = "Use db_query to monitor market_ticks for spread_pips > 100 and publish alert to Confluence"
    decision = select_blueprint(scenario, _intent_for(scenario))
    assert decision is not None
    assert decision.workflow_path.is_file()
