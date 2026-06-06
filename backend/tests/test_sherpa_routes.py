"""Sherpa slash route parsing and contextual suggestions."""
from __future__ import annotations

from copilot.llm_router import finalize_sherpa_route, route_sherpa_message
from copilot.sherpa_routes import list_sherpa_routes, parse_slash_route, route_message_with_slash


def test_parse_run_slash() -> None:
    route, body = parse_slash_route("/run")
    assert route is not None
    assert route.id == "run"
    assert body == ""


def test_parse_build_with_body() -> None:
    route, body = parse_slash_route("/build  Export leads to CSV")
    assert route is not None
    assert route.id == "build"
    assert "Export leads" in body


def test_slash_run_sets_wants_sample_run() -> None:
    wf = {"name": "Comms Export", "nodes": []}
    out = route_message_with_slash("/run", canvas_workflow=wf)
    assert out is not None
    assert out.metadata.get("wants_sample_run") is True
    assert out.source == "slash_route"


def test_slash_improve_sets_edit() -> None:
    wf = {"name": "Comms Export", "nodes": []}
    out = route_message_with_slash("/improve", canvas_workflow=wf)
    assert out is not None
    assert out.intent == "build"
    assert out.metadata.get("edit_existing_workflow") is True
    assert "Comms Export" in out.enhanced_question


def test_slash_check_run_intent() -> None:
    out = route_message_with_slash("/check-run How many rows exported?")
    assert out is not None
    assert out.intent == "explain_run"
    assert "How many rows" in out.enhanced_question


def test_list_suggests_run_after_build() -> None:
    listed = list_sherpa_routes(has_workflow=True, has_run_log=False)
    assert "run" in listed["suggested_ids"]
    assert "build" in listed["suggested_ids"]


def test_list_prioritizes_check_run_after_run() -> None:
    listed = list_sherpa_routes(has_workflow=True, has_run_log=True)
    assert listed["suggested_ids"][0] == "check-run"


def test_route_sherpa_message_heuristic_slash_without_gemini(monkeypatch) -> None:
    monkeypatch.setattr("copilot.llm_router.gemini_configured", lambda: False)
    out = route_sherpa_message(
        "/automate Daily at 9am",
        has_workflow=True,
        canvas_workflow={"name": "W", "nodes": []},
    )
    assert out.intent == "automate"
    assert out.source == "slash_route"


def test_finalize_preserves_slash_run() -> None:
    wf = {"name": "W", "nodes": []}
    forced = route_message_with_slash("/run", canvas_workflow=wf)
    assert forced is not None
    out = finalize_sherpa_route(forced, message="/run", canvas_workflow=wf)
    assert out.metadata.get("wants_sample_run") is True
