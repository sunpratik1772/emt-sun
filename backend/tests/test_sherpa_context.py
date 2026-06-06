"""Tests for unified Sherpa context resolver API."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_resolve_context_endpoint_returns_workflow_and_run() -> None:
    client = TestClient(app)
    resp = client.post(
        "/copilot/resolve-context",
        json={
            "route_metadata": {"run_selector": "current"},
            "current_workflow": {"name": "Test", "nodes": [{"id": "n1"}], "edges": []},
            "run_log": [{"node_id": "n1", "status": "ok"}],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["workflow"]["name"] == "Test"
    assert len(body["run_log"]) == 1
