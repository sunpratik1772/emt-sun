"""Tests for copilot workflow load streaming."""
from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.database import delete_workflow_db, init_db, save_workflow_db
from app.main import app
from copilot.workflow_loader import extract_workflow_search_query, is_load_workflow_request


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


def test_is_load_workflow_request():
    assert is_load_workflow_request("Load the revenue pipeline workflow")
    assert is_load_workflow_request('Load "Orders Top Contributors Excel Report" onto the canvas')
    assert not is_load_workflow_request("Build a revenue pipeline")


def test_extract_workflow_search_query():
    assert extract_workflow_search_query("Load the revenue pipeline") == "revenue pipeline"
    assert (
        extract_workflow_search_query('Load "Orders Top Contributors Excel Report" onto the canvas')
        == "Orders Top Contributors Excel Report"
    )


def test_load_stream_single_match():
    client = TestClient(app)
    fname = f"load-stream-{uuid.uuid4().hex[:8]}.json"
    dag = {
        "workflow_id": "wf_load_stream",
        "name": "Zephyr Unique Load Test Pipeline",
        "nodes": [{"id": "n1", "type": "passthrough"}],
        "edges": [],
    }
    from app.user_scope import SEED_USER_ID

    save_workflow_db(
        filename=fname,
        workflow_id=dag["workflow_id"],
        name=dag["name"],
        description="Unique load stream test",
        workflow_data=json.dumps(dag),
        user_id=SEED_USER_ID,
    )
    try:
        resp = client.post(
            "/copilot/load/stream",
            json={"message": "Load zephyr unique load test pipeline"},
        )
        assert resp.status_code == 200
        body = resp.text
        assert "workflow_created" in body
        assert "Zephyr Unique Load Test Pipeline" in body
    finally:
        delete_workflow_db(fname, SEED_USER_ID)


def test_classify_routes_load_heuristic():
    client = TestClient(app)
    resp = client.post(
        "/copilot/classify",
        json={"message": "Open the leads pipeline workflow", "has_workflow": False},
    )
    assert resp.status_code == 200
    assert resp.json()["intent"] == "load"
