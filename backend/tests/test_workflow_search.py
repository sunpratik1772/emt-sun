"""Tests for workflow name search / disambiguation."""
from __future__ import annotations

import json
import uuid

import pytest

from app.database import delete_workflow_db, init_db, save_workflow_db
from app.main import app
from app.workflow_search import search_workflows
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _db_ready():
    init_db()
    yield


def _row(filename: str, name: str, **extra) -> dict:
    dag = {
        "workflow_id": extra.get("workflow_id", f"wf_{filename}"),
        "name": name,
        "description": extra.get("description", ""),
        "nodes": [],
        "edges": [],
    }
    return {
        "filename": filename,
        "workflow_id": dag["workflow_id"],
        "name": name,
        "description": dag.get("description"),
        "workflow_data": json.dumps(dag),
    }


def test_search_single_match_loads_directly():
    rows = [
        _row("leads-pipeline.json", "Leads Pipeline", description="Hot/cold lead scoring"),
        _row("revenue-report.json", "Revenue Report"),
    ]
    result = search_workflows(rows, "leads pipeline")
    assert result["action"] == "load"
    assert result["match"]["filename"] == "leads-pipeline.json"
    assert result["workflow"]["name"] == "Leads Pipeline"


def test_search_returns_top_three_disambiguation():
    rows = [
        _row("leads-v1.json", "Leads Pipeline v1"),
        _row("leads-v2.json", "Leads Pipeline v2"),
        _row("leads-v3.json", "Leads Pipeline v3"),
        _row("revenue.json", "Revenue Summary"),
    ]
    result = search_workflows(rows, "leads pipeline", limit=3)
    assert result["action"] == "disambiguate"
    assert len(result["matches"]) == 3
    assert all("leads" in m["name"].lower() for m in result["matches"])


def test_search_not_found():
    rows = [_row("alpha.json", "Alpha Workflow")]
    result = search_workflows(rows, "nonexistent xyz workflow")
    assert result["action"] == "not_found"
    assert result["matches"] == []


def test_search_api_endpoint():
    client = TestClient(app)
    filename = f"search-test-{uuid.uuid4().hex[:8]}.json"
    dag = {
        "workflow_id": "wf_search_test",
        "name": "Surveillance Alert Triage",
        "description": "Triage alerts from db_query",
        "nodes": [{"id": "n1", "type": "passthrough"}],
        "edges": [],
    }
    save_workflow_db(
        filename=filename,
        workflow_id=dag["workflow_id"],
        name=dag["name"],
        description=dag["description"],
        workflow_data=json.dumps(dag),
    )
    try:
        resp = client.get("/workflows/search", params={"q": "surveillance alert triage"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["action"] == "load"
        assert body["match"]["filename"] == filename
    finally:
        delete_workflow_db(filename)
