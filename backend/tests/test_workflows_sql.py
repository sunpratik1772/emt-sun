from __future__ import annotations

import os
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import (
    init_db,
    save_workflow_db,
    get_workflow_db,
    get_workflow_by_name_db,
    delete_workflow_db,
    list_workflows_db,
    save_draft_db,
    get_draft_db,
    delete_draft_db,
    list_drafts_db,
    list_workflow_library_rows,
)
from app.deps import WORKFLOWS_DIR, DRAFTS_DIR
from app.user_scope import SEED_USER_ID

UID = SEED_USER_ID


@pytest.fixture(autouse=True)
def setup_teardown_db():
    init_db()
    yield
    for fname in ["test_api_workflow.json", "promoted_test_wf.json", "test_draft_for_promote.json"]:
        try:
            delete_workflow_db(fname, UID)
        except Exception:
            pass
        try:
            delete_draft_db(fname, UID)
        except Exception:
            pass


def test_workflows_db_direct_crud() -> None:
    filename = f"test_direct_{uuid.uuid4().hex[:8]}.json"
    workflow_id = "wf_direct_123"
    name = "Direct DB Workflow Test"
    description = "A direct SQL db CRUD test workflow"
    dag = {
        "workflow_id": workflow_id,
        "name": name,
        "description": description,
        "nodes": [{"id": "n1", "type": "passthrough"}],
        "edges": []
    }
    workflow_data = json.dumps(dag)

    # 1. Save to DB
    save_workflow_db(
        filename=filename,
        workflow_id=workflow_id,
        name=name,
        description=description,
        workflow_data=workflow_data,
        user_id=UID,
    )

    # 2. Get and Assert
    row = get_workflow_db(filename, UID)
    assert row is not None
    assert row["filename"] == filename
    assert row["workflow_id"] == workflow_id
    assert row["name"] == name
    assert row["description"] == description
    assert json.loads(row["workflow_data"]) == dag

    # 3. Verify in List
    all_workflows = list_workflows_db(UID)
    found = next((w for w in all_workflows if w["filename"] == filename), None)
    assert found is not None
    assert found["workflow_id"] == workflow_id

    # 4. Delete and Assert
    delete_workflow_db(filename, UID)
    assert get_workflow_db(filename, UID) is None


def test_workflows_router_crud(auth_client: TestClient) -> None:
    client = auth_client
    filename = "test_api_workflow.json"
    dag = {
        "workflow_id": "wf_api_999",
        "name": "API Sync Workflow Test",
        "description": "Integration test for DB-only CRUD",
        "nodes": [{"id": "n1", "type": "passthrough"}, {"id": "n2", "type": "excel_output"}],
        "edges": [{"source": "n1", "target": "n2"}]
    }

    # 1. Save workflow via API
    resp_save = client.post(f"/workflows/{filename}", json=dag)
    assert resp_save.status_code == 200
    assert resp_save.json()["location"] == "workflows"

    db_row = get_workflow_db(filename, UID)
    assert db_row is not None
    assert db_row["workflow_id"] == "wf_api_999"
    assert json.loads(db_row["workflow_data"]) == dag

    resp_get = client.get(f"/workflows/{filename}")
    assert resp_get.status_code == 200
    assert resp_get.json()["workflow_id"] == "wf_api_999"

    # 5. Check List endpoint (GET /workflows) and verify merged count/items
    resp_list = client.get("/workflows")
    assert resp_list.status_code == 200
    wfs = resp_list.json()["workflows"]
    found = next((w for w in wfs if w["filename"] == filename), None)
    assert found is not None
    assert found["name"] == "API Sync Workflow Test"
    assert found["node_count"] == 2

    resp_del = client.delete(f"/workflows/{filename}")
    assert resp_del.status_code == 200
    assert get_workflow_db(filename, UID) is None


def test_save_workflow_rejects_duplicate_display_name(auth_client: TestClient) -> None:
    client = auth_client
    first = "name_conflict_a.json"
    second = "name_conflict_b.yaml"
    shared_name = "Duplicate Display Name Test"
    dag_a = {
        "workflow_id": "wf_dup_a",
        "name": shared_name,
        "nodes": [{"id": "n1", "type": "passthrough"}],
        "edges": [],
    }
    dag_b = {
        "workflow_id": "wf_dup_b",
        "name": shared_name,
        "nodes": [{"id": "n1", "type": "passthrough"}, {"id": "n2", "type": "passthrough"}],
        "edges": [],
    }
    try:
        assert client.post(f"/workflows/{first}", json=dag_a).status_code == 200
        resp_conflict = client.post(f"/workflows/{second}", json=dag_b)
        assert resp_conflict.status_code == 409
        detail = resp_conflict.json()["detail"]
        assert detail["code"] == "workflow_name_conflict"
        assert len(detail["conflicts"]) == 1
        assert detail["conflicts"][0]["filename"] == first

        resp_replace = client.post(f"/workflows/{second}", json=dag_b, params={"replace": True})
        assert resp_replace.status_code == 200
        assert get_workflow_db(first, UID) is None
        assert get_workflow_db(second, UID) is not None
    finally:
        delete_workflow_db(first, UID)
        delete_workflow_db(second, UID)


def test_promote_draft_sql_sync(auth_client: TestClient) -> None:
    client = auth_client
    draft_filename = "test_draft_for_promote.json"
    target_filename = "promoted_test_wf.json"

    dag = {
        "workflow_id": "wf_draft_111",
        "name": "Draft Workflow to Promote",
        "description": "Transient draft workflow",
        "nodes": [{"id": "n1", "type": "passthrough"}],
        "edges": [],
    }

    save_draft_db(
        filename=draft_filename,
        workflow_id=dag["workflow_id"],
        name=dag["name"],
        description=dag["description"],
        workflow_data=json.dumps(dag),
        user_id=UID,
    )

    promote_payload = {
        "target_filename": target_filename,
        "name": "Newly Promoted Workflow Name",
    }
    resp_promote = client.post(f"/drafts/{draft_filename}/promote", json=promote_payload)
    assert resp_promote.status_code == 200
    assert resp_promote.json()["saved_as"] == target_filename

    assert get_draft_db(draft_filename, UID) is None

    db_row = get_workflow_db(target_filename, UID)
    assert db_row is not None
    assert db_row["name"] == "Newly Promoted Workflow Name"
    assert json.loads(db_row["workflow_data"])["workflow_id"] == "wf_draft_111"

    delete_workflow_db(target_filename, UID)


def test_drafts_db_direct_crud() -> None:
    filename = f"test_draft_{uuid.uuid4().hex[:8]}.json"
    dag = {
        "workflow_id": "wf_draft_direct",
        "name": "Draft DB Test",
        "description": "Transient draft in SQL",
        "nodes": [{"id": "n1", "type": "passthrough"}],
        "edges": [],
    }
    save_draft_db(
        filename=filename,
        workflow_id=dag["workflow_id"],
        name=dag["name"],
        description=dag["description"],
        workflow_data=json.dumps(dag),
        user_id=UID,
    )
    try:
        row = get_draft_db(filename, UID)
        assert row is not None
        assert json.loads(row["workflow_data"]) == dag
        listed = list_drafts_db(UID)
        assert any(d["filename"] == filename for d in listed)
    finally:
        delete_draft_db(filename, UID)
        assert get_draft_db(filename, UID) is None


def test_workflow_exists_in_library_finds_draft_only() -> None:
    from app.database import workflow_exists_in_library

    filename = f"draft_exists_{uuid.uuid4().hex[:8]}.json"
    name = "Sherpa Draft Exists Check"
    dag = {
        "workflow_id": "wf_draft_exists",
        "name": name,
        "nodes": [{"id": "n1", "type": "passthrough"}],
        "edges": [],
    }
    save_draft_db(
        filename=filename,
        workflow_id=dag["workflow_id"],
        name=name,
        description=None,
        workflow_data=json.dumps(dag),
        user_id=UID,
    )
    try:
        assert workflow_exists_in_library(name, UID) is True
        assert workflow_exists_in_library("nonexistent workflow xyz", UID) is False
    finally:
        delete_draft_db(filename, UID)


def test_get_workflow_by_name_finds_draft_only() -> None:
    filename = f"draft_only_{uuid.uuid4().hex[:8]}.json"
    name = "Sherpa Draft Only Pipeline"
    dag = {
        "workflow_id": "wf_draft_only",
        "name": name,
        "nodes": [{"id": "n1", "type": "passthrough"}],
        "edges": [],
    }
    save_draft_db(
        filename=filename,
        workflow_id=dag["workflow_id"],
        name=name,
        description=None,
        workflow_data=json.dumps(dag),
        user_id=UID,
    )
    try:
        resolved = get_workflow_by_name_db(name, UID)
        assert resolved is not None
        assert resolved.get("name") == name
        kinds = {r.get("_library_kind") for r in list_workflow_library_rows(UID) if r.get("name") == name}
        assert "draft" in kinds
    finally:
        delete_draft_db(filename, UID)
