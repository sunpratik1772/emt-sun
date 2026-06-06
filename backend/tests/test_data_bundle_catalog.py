"""Tests for registry-backed Excel blueprint catalog."""
from __future__ import annotations

from engine.data_bundle_catalog import (
    all_bundle_ids,
    build_join_excel_skeleton,
    build_load_spec,
    build_single_bundle_excel_skeleton,
    datasets_in_scenario,
    excel_filename_for,
    resolve_join_pair,
)


def test_all_registry_bundles_have_load_specs() -> None:
    for bundle_id in all_bundle_ids():
        spec = build_load_spec(bundle_id)
        assert spec.node_type == "db_query"
        assert spec.config


def test_demo_bundle_uses_db_query() -> None:
    spec = build_load_spec("orders.csv")
    assert spec.node_type == "db_query"
    assert spec.config["source"] == "orders.csv"
    assert "orders" in spec.config["query"]


def test_db_bundle_uses_db_query() -> None:
    spec = build_load_spec("hs_alerts")
    assert spec.node_type == "db_query"
    assert "hs_alerts" in spec.config["query"]


def test_resolve_known_join_pair() -> None:
    pair = resolve_join_pair(["hs_alerts", "market_ticks"])
    assert pair is not None
    assert pair.left_key == "alert_id"
    assert pair.right_key == "alert_id"


def test_resolve_orders_products_demo_file() -> None:
    pair = resolve_join_pair(["orders.csv", "products.csv"])
    assert pair is not None
    assert pair.demo_filename == "studio_04_product_360_join.json"


def test_single_bundle_excel_skeleton() -> None:
    wf = build_single_bundle_excel_skeleton("leads.csv", "leads_export.xlsx")
    types = [n["type"] for n in wf["nodes"]]
    assert types == ["manual_trigger", "db_query", "excel_output"]
    export = next(n for n in wf["nodes"] if n["type"] == "excel_output")
    assert export["config"]["filename"] == "leads_export.xlsx"


def test_join_excel_skeleton() -> None:
    pair = resolve_join_pair(["hs_alerts", "market_ticks"])
    assert pair is not None
    wf = build_join_excel_skeleton(pair, "AlertsMarketData.xlsx")
    types = [n["type"] for n in wf["nodes"]]
    assert "join" in types
    assert "excel_output" in types
    assert wf["edges"][-1]["to"] == "export"


def test_excel_filename_from_scenario() -> None:
    scenario = "join hs_alerts and market_ticks to AlertsMarketData.xlsx"
    assert excel_filename_for(["hs_alerts", "market_ticks"], scenario) == "AlertsMarketData.xlsx"


def test_datasets_in_scenario_aliases() -> None:
    found = datasets_in_scenario("Load orders and products into excel")
    assert "orders.csv" in found
    assert "products.csv" in found
