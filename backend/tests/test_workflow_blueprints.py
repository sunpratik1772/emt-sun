"""Tests for leads workflow blueprints and harness intent fixes."""
from __future__ import annotations

from copilot.workflow_blueprints import (
    LEADS_HIGH_RISK_EXPRESSION,
    build_leads_filter_csv_skeleton,
    build_leads_sort_csv_skeleton,
)
from generation.harness.blueprint_router import select_blueprint
from generation.harness.enrichment import known_datasets
from generation.harness.intent import classify


def test_leads_sort_skeleton_topology() -> None:
    wf = build_leads_sort_csv_skeleton()
    types = [n["type"] for n in wf["nodes"]]
    assert types == ["manual_trigger", "db_query", "sort", "csv_output"]
    sort_node = next(n for n in wf["nodes"] if n["type"] == "sort")
    assert sort_node["config"]["sortBy"] == "score"
    assert sort_node["config"]["order"] == "desc"


def test_leads_filter_skeleton_uses_high_risk_glossary() -> None:
    wf = build_leads_filter_csv_skeleton()
    filt = next(n for n in wf["nodes"] if n["type"] == "filter")
    assert filt["config"]["expression"] == LEADS_HIGH_RISK_EXPRESSION


def test_classify_leads_from_does_not_match_fro_scenario() -> None:
    intent = classify(
        "Extract data from leads.csv, sort by score descending, then csv_output.",
        known_datasets=known_datasets(),
        known_node_types={"sort", "csv_output", "db_query"},
    )
    assert "fro" not in intent.scenarios
    assert "leads.csv" in intent.datasets
    assert "sort" in intent.actions
    assert "csv_output" in intent.node_types


def test_blueprint_selects_leads_filter_pattern() -> None:
    intent = classify(
        "Load leads.csv, filter high-risk rows, and export a CSV summary.",
        known_datasets=known_datasets(),
    )
    decision = select_blueprint(
        "Load leads.csv, filter high-risk rows, and export a CSV summary.",
        intent,
    )
    assert decision is not None
    assert decision.blueprint_id == "leads_filter_csv"
