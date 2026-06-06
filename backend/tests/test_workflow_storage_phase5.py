"""Tests for DB-backed copilot/scheduler workflow persistence."""
from __future__ import annotations

import json
import uuid

import pytest

from app.database import delete_workflow_db, get_workflow_db, init_db
from copilot.automation_agent import save_workflow_for_automation


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


def test_automation_save_workflow_uses_db_only():
    filename_prefix = f"auto-save-{uuid.uuid4().hex[:6]}"
    dag = {
        "workflow_id": f"wf_{filename_prefix}",
        "name": f"Automation Save {filename_prefix}",
        "description": "Saved via automation agent",
        "nodes": [{"id": "n1", "type": "passthrough"}],
        "edges": [],
    }
    saved = save_workflow_for_automation(dag)
    try:
        row = get_workflow_db(saved)
        assert row is not None
        assert json.loads(row["workflow_data"])["workflow_id"] == dag["workflow_id"]
    finally:
        delete_workflow_db(saved)
