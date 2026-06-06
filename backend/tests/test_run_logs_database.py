"""Unit/integration tests for the SQL-backed run_logs database table."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
import pytest
import requests

from app.database import save_run_log, list_db_run_logs, clear_db_run_logs, list_run_artifacts, init_db

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"


def test_database_direct_crud() -> None:
    init_db()
    # 1. Clear database
    clear_db_run_logs()
    assert len(list_db_run_logs()) == 0

    # 2. Insert mock log entry
    run_id = f"test_run_{uuid.uuid4().hex[:8]}"
    entry = {
        "run_id": run_id,
        "workflow": "test_workflow_db.json",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": 1250,
        "status": "success",
        "disposition": "REVIEW",
        "node_count": 5,
        "edge_count": 4,
        "flag_count": 2,
        "error": None,
        "report_path": "/tmp/reports/test.html",
        "download_url": "http://localhost:8001/download/test.html",
        "run_log": [
            {
                "node_id": "n1",
                "node_type": "ALERT_TRIGGER",
                "label": "Alert Trigger",
                "index": 1,
                "total": 2,
                "status": "ok",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "duration_ms": 15,
                "input": {"input": []},
                "output": {"node_output": {"triggered": True, "payload": {"alert_id": "A-1"}}},
            }
        ],
        "run_result": {"disposition": "REVIEW", "flag_count": 2},
        "run_error": None,
    }
    save_run_log(entry)

    # 3. Retrieve and assert values
    logs = list_db_run_logs()
    assert len(logs) >= 1
    found = next((log for log in logs if log["run_id"] == run_id), None)
    assert found is not None
    assert found["workflow"] == "test_workflow_db.json"
    assert found["duration_ms"] == 1250
    assert found["status"] == "success"
    assert found["disposition"] == "REVIEW"
    assert found["node_count"] == 5
    assert found["edge_count"] == 4
    assert found["flag_count"] == 2
    assert found["report_path"] == "/tmp/reports/test.html"
    assert found["download_url"] == "http://localhost:8001/download/test.html"
    assert isinstance(found.get("run_log"), list)
    assert found["run_log"][0]["node_id"] == "n1"
    assert isinstance(found.get("run_result"), dict)
    assert found["run_result"]["disposition"] == "REVIEW"
    assert isinstance(found.get("artifacts"), list)
    assert any((a.get("file_name") or "").endswith("test.html") for a in found["artifacts"])
    db_artifacts = list_run_artifacts(run_id)
    assert len(db_artifacts) >= 1

    # 4. Clear and verify empty
    clear_db_run_logs()
    assert len(list_db_run_logs()) == 0


def test_run_logs_endpoints() -> None:
    # Use requests to verify HTTP endpoints hit the database correctly
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})

    # 1. Clear via API
    r_clear = s.delete(f"{API}/run-logs", timeout=10)
    assert r_clear.status_code == 200

    # 2. Check empty list
    r_list = s.get(f"{API}/run-logs", timeout=10)
    assert r_list.status_code == 200
    assert r_list.json()["total"] == 0
    assert len(r_list.json()["logs"]) == 0

    # 3. Post a run log via API
    run_id = f"api_run_{uuid.uuid4().hex[:8]}"
    entry = {
        "run_id": run_id,
        "workflow": "api_workflow_test.yaml",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": 789,
        "status": "error",
        "disposition": "ESCALATE",
        "node_count": 3,
        "edge_count": 2,
        "flag_count": 0,
        "error": "Division by zero",
        "report_path": None,
        "download_url": None,
        "run_log": [
            {
                "node_id": "extract",
                "node_type": "CSV_EXTRACT",
                "label": "Extract CSV",
                "index": 1,
                "total": 1,
                "status": "error",
                "duration_ms": 5,
                "output": {"node_output": {"rows": []}},
                "error": "Division by zero",
            }
        ],
        "run_result": None,
        "run_error": "Division by zero",
    }
    r_post = s.post(f"{API}/run-logs", json=entry, timeout=10)
    assert r_post.status_code == 200
    assert r_post.json().get("ok") is True

    # 4. Fetch list and assert
    r_list2 = s.get(f"{API}/run-logs", timeout=10)
    assert r_list2.status_code == 200
    data = r_list2.json()
    assert data["total"] >= 1
    found = next((log for log in data["logs"] if log["run_id"] == run_id), None)
    assert found is not None
    assert found["workflow"] == "api_workflow_test.yaml"
    assert found["status"] == "error"
    assert found["error"] == "Division by zero"
    assert found["disposition"] == "ESCALATE"
    assert isinstance(found.get("run_log"), list)
    assert found["run_log"][0]["node_id"] == "extract"
    assert found.get("run_error") == "Division by zero"
    assert isinstance(found.get("artifacts"), list)
