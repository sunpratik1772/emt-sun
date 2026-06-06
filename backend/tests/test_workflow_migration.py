"""Smoke test for legacy workflow file import into DB."""
from __future__ import annotations

import json
import uuid

import pytest

from app.database import delete_workflow_db, get_workflow_db, init_db
from app.deps import WORKFLOWS_DIR
from app.user_scope import SEED_USER_ID


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


def test_legacy_workflow_file_imported_to_db():
    fname = f"legacy-import-{uuid.uuid4().hex[:8]}.json"
    path = WORKFLOWS_DIR / fname
    dag = {
        "workflow_id": "wf_legacy",
        "name": "Legacy Import Test",
        "nodes": [],
        "edges": [],
    }
    path.write_text(json.dumps(dag))
    try:
        delete_workflow_db(fname, SEED_USER_ID)
        init_db()
        row = get_workflow_db(fname, SEED_USER_ID)
        assert row is not None
        assert row["name"] == "Legacy Import Test"
    finally:
        delete_workflow_db(fname, SEED_USER_ID)
        if path.exists():
            path.unlink()
