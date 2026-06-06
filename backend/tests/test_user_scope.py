from __future__ import annotations

import json
import uuid

from app.database import get_user_by_id, init_db, save_workflow_db, get_workflow_db
from app.database_scope import (
    cast_workflow_vote,
    get_user_by_username,
    list_accessible_data_source_ids,
    list_accessible_skill_ids,
)
from app.user_scope import SEED_EMAIL, SEED_NAME, SEED_USER_ID, SEED_USERNAME


def test_seed_user_exists_with_username_password() -> None:
    init_db()
    user = get_user_by_username(SEED_USERNAME)
    assert user is not None
    assert user["user_id"] == SEED_USER_ID
    assert user["email"] == SEED_EMAIL
    assert user["name"] == SEED_NAME
    assert user.get("password_hash")


def test_seed_user_has_default_data_source_and_skill_access() -> None:
    init_db()
    sources = list_accessible_data_source_ids(SEED_USER_ID)
    skills = list_accessible_skill_ids(SEED_USER_ID)
    assert len(sources) >= 1
    assert len(skills) >= 1


def test_upvote_promotes_workflow_to_good_examples() -> None:
    init_db()
    filename = f"vote_test_{uuid.uuid4().hex[:8]}.json"
    dag = {
        "workflow_id": "wf_vote",
        "name": "Vote Test Workflow",
        "nodes": [{"id": "n1", "type": "passthrough"}],
        "edges": [],
    }
    save_workflow_db(
        filename=filename,
        workflow_id=dag["workflow_id"],
        name=dag["name"],
        description=None,
        workflow_data=json.dumps(dag),
        user_id=SEED_USER_ID,
    )
    try:
        result = cast_workflow_vote(SEED_USER_ID, SEED_USER_ID, filename, "up")
        assert result["vote"] == "up"
        assert result["upvote_count"] >= 1
        assert result["promoted"] is not None
        row = get_workflow_db(filename, SEED_USER_ID)
        assert row is not None
        assert int(row.get("upvote_count") or 0) >= 1
    finally:
        from app.database import delete_workflow_db

        delete_workflow_db(filename, SEED_USER_ID)
