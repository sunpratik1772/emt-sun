"""Run-review thinking monologue for explain_run route."""
from __future__ import annotations

from copilot.build_narration import build_run_review_monologue
from tests.thinking_fake_adapter import ThinkingFakeAdapter


def test_reliability_review_monologue(monkeypatch) -> None:
    monkeypatch.setattr("copilot.thinking_monologue.gemini_configured", lambda: True)
    msg = (
        'Review the latest run of "Join Comms Messages with HS Alerts and Rank" '
        "and suggest one change to improve reliability."
    )
    workflow = {"name": "Join Comms Messages with HS Alerts and Rank"}
    run_log = [
        {"node_id": "n1", "status": "ok"},
        {"node_id": "n2", "status": "ok"},
        {"node_id": "n3", "status": "ok"},
    ]
    text = build_run_review_monologue(
        msg,
        workflow,
        run_log,
        route_metadata={"run_selector": "latest", "workflow_name": workflow["name"]},
        adapter=ThinkingFakeAdapter(),
    )
    assert "User asked:" not in text
    assert "Join Comms Messages with HS Alerts and Rank" in text or "run log" in text.lower()
    assert "pipeline should work" not in text.lower()
    assert "maps to" not in text.lower()
