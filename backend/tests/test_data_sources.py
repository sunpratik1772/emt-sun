"""DataSourceRegistry loads YAML metadata correctly."""
from __future__ import annotations

from connectors import get_registry


def test_registry_loads_all_sources():
    reg = get_registry()
    ids = {s.id for s in reg.all()}
    required = {"hs_alerts", "hs_orders", "hs_exec", "hs_trades", "market_ticks", "comms_messages"}
    assert required <= ids
    assert "orders.csv" in ids


def test_all_sources_use_oracle_connector():
    from connectors.base import ConnectorKind

    for source in get_registry().all():
        assert source.connector == ConnectorKind.ORACLE
        assert source.sources
        assert str(source.sources[0]).startswith("oracle:")


def test_orders_and_exec_have_expected_columns():
    orders = get_registry().get("hs_orders")
    assert orders is not None
    names = set(orders.column_names())
    for expected in ("trader_id", "order_id", "order_time", "quantity", "limit_price", "side", "book"):
        assert expected in names, f"missing column {expected}"

    execs = get_registry().get("hs_exec")
    assert execs is not None
    exec_names = set(execs.column_names())
    for expected in ("exec_id", "order_id", "exec_time", "exec_quantity", "exec_price", "trade_version"):
        assert expected in exec_names, f"missing column {expected}"


def test_semantic_tag_lookup():
    """The 'size' semantic maps per selected source."""
    reg = get_registry()
    orders_size = reg.get("hs_orders").semantic_map()["size"]
    executions_size = reg.get("hs_exec").semantic_map()["size"]
    market_size = [c.name for c in reg.get("market_ticks").columns if c.semantic == "size"]
    assert orders_size == ["quantity"]
    assert executions_size == ["exec_quantity"]
    assert set(market_size) == {"bid_size", "ask_size"}


def test_unknown_source_returns_none():
    assert get_registry().get("does-not-exist") is None


def test_registry_endpoint_shape():
    """The JSON shape is stable — anyone reading /data_sources relies on it."""
    doc = get_registry().to_json()
    assert "sources" in doc
    for s in doc["sources"]:
        assert {"id", "description", "sources", "columns"} <= set(s.keys())
        for c in s["columns"]:
            assert {"name", "type", "description", "semantic", "optional"} <= set(c.keys())


# ---------------------------------------------------------------------------
# semantic_map
# ---------------------------------------------------------------------------

def test_semantic_map_returns_correct_columns():
    orders = get_registry().get("hs_orders")
    sm = orders.semantic_map()
    assert sm["trader"] == ["participant_id", "trader_id"]
    assert sm["size"] == ["quantity"]
    assert sm["price"] == ["limit_price"]
    assert sm["time"] == ["order_time"]


def test_semantic_map_multi_column():
    """market_ticks.price maps to bid, ask, mid — all three in order."""
    market = get_registry().get("market_ticks")
    sm = market.semantic_map()
    assert set(sm["price"]) == {"bid", "ask", "mid"}


def test_semantic_map_empty_when_no_tags():
    """comms text-only fields without semantic tags do not appear in the map."""
    comms = get_registry().get("comms_messages")
    sm = comms.semantic_map()
    assert "display_post" not in sm


# ---------------------------------------------------------------------------
# resolve_field
# ---------------------------------------------------------------------------


def test_resolve_field_direct_column():
    orders = get_registry().get("hs_orders")
    assert orders.resolve_field("trader_id") == "trader_id"
    assert orders.resolve_field("quantity") == "quantity"


def test_resolve_field_semantic_alias():
    assert get_registry().get("hs_orders").resolve_field("size") == "quantity"
    assert get_registry().get("hs_exec").resolve_field("size") == "exec_quantity"
    assert get_registry().get("hs_exec").resolve_field("trader") == "participant_id"


def test_resolve_field_multi_semantic_uses_first():
    market = get_registry().get("market_ticks")
    assert market.resolve_field("price") in ("bid", "ask", "mid")
    first = market.semantic_map()["price"][0]
    assert market.resolve_field("price") == first


def test_resolve_field_unknown():
    assert get_registry().get("hs_orders").resolve_field("does_not_exist") is None
    assert get_registry().get("hs_orders").resolve_field("") is None

    alerts = get_registry().get("hs_alerts")
    assert alerts.resolve_field("alert_id") == "alert_id"
    assert alerts.resolve_field("nope") is None


# ---------------------------------------------------------------------------
# schema_hint / schema_hints_for_prompt
# ---------------------------------------------------------------------------

def test_schema_hint_contains_column_names():
    hint = get_registry().get("hs_orders").schema_hint()
    assert "trader_id" in hint
    assert "hs_orders" in hint
    assert "quantity" in hint
    assert "semantic: size" in hint


def test_schema_hints_for_prompt_covers_all_sources():
    hints = get_registry().schema_hints_for_prompt()
    for source_id in ("hs_alerts", "hs_orders", "hs_exec", "hs_trades", "market_ticks", "comms_messages"):
        assert source_id in hints


def test_schema_hints_for_prompt_warns_against_aliases():
    """The instruction block must tell the LLM to use exact column names."""
    hints = get_registry().schema_hints_for_prompt()
    assert "exact column names" in hints.lower() or "ONLY" in hints
