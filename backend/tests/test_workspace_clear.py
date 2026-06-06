from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.database import (
    list_automations,
    list_drafts_db,
    list_workflows_db,
    save_automation,
    save_chat,
    save_draft_db,
    save_run_log,
    save_workflow_db,
)
from app.user_scope import SEED_USER_ID

UID = SEED_USER_ID


def test_clear_workspace_wipes_user_data_but_not_auth(auth_client: TestClient) -> None:
    client = auth_client

    save_workflow_db(
        filename="wf_clear_test.json",
        workflow_id="wf1",
        name="Test",
        description=None,
        workflow_data=json.dumps({"workflow_id": "wf1", "name": "Test", "nodes": [], "edges": []}),
        user_id=UID,
    )
    save_draft_db(
        filename="draft_clear_test.json",
        workflow_id="wf2",
        name="Draft",
        description=None,
        workflow_data=json.dumps({"workflow_id": "wf2", "name": "Draft", "nodes": [], "edges": []}),
        user_id=UID,
    )
    save_chat(UID, UID, "Chat", [{"role": "user", "content": "hi", "timestamp": "2026-01-01T00:00:00Z"}])
    save_run_log(
        {
            "run_id": "run_clear_1",
            "workflow": "wf_clear_test.json",
            "started_at": "2026-01-01T00:00:00Z",
            "status": "ok",
            "user_id": UID,
        }
    )
    save_automation(
        automation_id="auto_clear_1",
        name="Auto",
        workflow_filename="wf_clear_test.json",
        schedule_type="cron",
        cron_expression="0 9 * * *",
        interval_mins=None,
        duration_mins=None,
        active=False,
        author="test",
        user_id=UID,
        output_filename_pattern=None,
    )

    resp = client.delete("/workspace")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "good_examples" in body["preserved"]
    assert list_workflows_db(UID) == []
    assert list_drafts_db(UID) == []
    assert list_automations(UID) == []
