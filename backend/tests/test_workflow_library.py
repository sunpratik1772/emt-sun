"""Canonical workflow catalog — one display name per library row."""
from __future__ import annotations

import json
import uuid

from app.database import delete_draft_db, save_draft_db
from app.user_scope import SEED_USER_ID
from app.workflow_library import (
    build_workflow_catalog,
    catalog_lookup_exact,
    resolve_workflow_by_display_name,
    workflow_exists_in_catalog,
)

UID = SEED_USER_ID


def test_catalog_dedupes_case_insensitive_names() -> None:
    a = f"dup_a_{uuid.uuid4().hex[:8]}.json"
    b = f"dup_b_{uuid.uuid4().hex[:8]}.json"
    name = "Orders Top Contributors Excel Report"
    dag = {
        "workflow_id": "wf_dup",
        "name": name,
        "nodes": [{"id": "n1", "type": "passthrough"}],
        "edges": [],
    }
    save_draft_db(
        filename=a,
        workflow_id=dag["workflow_id"],
        name=name.lower(),
        description=None,
        workflow_data=json.dumps({**dag, "name": name.lower()}),
        user_id=UID,
    )
    save_draft_db(
        filename=b,
        workflow_id=dag["workflow_id"],
        name=name,
        description=None,
        workflow_data=json.dumps(dag),
        user_id=UID,
    )
    try:
        catalog = build_workflow_catalog(UID)
        keys = [e.canonical_name.casefold() for e in catalog if e.canonical_name.casefold() == name.casefold()]
        assert len(keys) == 1
        assert catalog_lookup_exact(name, UID) is not None
        assert catalog_lookup_exact(name, UID).canonical_name == name
    finally:
        delete_draft_db(a, UID)
        delete_draft_db(b, UID)


def test_resolve_returns_canonical_name_for_fuzzy_query() -> None:
    filename = f"catalog_resolve_{uuid.uuid4().hex[:8]}.json"
    canonical = "Excel Report: Orders Top Contributors"
    dag = {
        "workflow_id": "wf_cat",
        "name": canonical,
        "nodes": [{"id": "n1", "type": "passthrough"}],
        "edges": [],
    }
    save_draft_db(
        filename=filename,
        workflow_id=dag["workflow_id"],
        name=canonical,
        description=None,
        workflow_data=json.dumps(dag),
        user_id=UID,
    )
    try:
        resolved = resolve_workflow_by_display_name(canonical, UID)
        assert resolved.get("action") == "load"
        assert resolved.get("canonical_name") == canonical
        assert resolved["workflow"]["name"] == canonical
        assert workflow_exists_in_catalog(canonical, UID) is True
    finally:
        delete_draft_db(filename, UID)
