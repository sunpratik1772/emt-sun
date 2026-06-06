from __future__ import annotations

import time
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from server import app
from app.database import (
    init_db,
    list_automations,
    get_automation,
    save_automation,
    delete_automation,
    list_automation_runs,
)
from app.scheduler import match_cron


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


def test_cron_matching():
    # Test cron matching functionality
    dt = datetime(2026, 5, 24, 11, 0, 0, tzinfo=timezone.utc)
    
    assert match_cron("0 11 * * *", dt) is True
    assert match_cron("*/5 * * * *", dt) is True  # 0 % 5 == 0
    assert match_cron("0 12 * * *", dt) is False
    assert match_cron("invalid cron expression", dt) is False


def test_database_crud():
    auto_id = "test_auto_uuid_123"
    
    # Save a test automation
    save_automation(
        automation_id=auto_id,
        name="Test Auto",
        workflow_filename="studio_01_mcp_ticket_swarm.json",
        schedule_type="cron",
        cron_expression="*/2 * * * *",
        interval_mins=2,
        duration_mins=30,
        active=True,
        author="Shalini Barman Roy",
    )
    
    # Retrieve it
    retrieved = get_automation(auto_id)
    assert retrieved is not None
    assert retrieved["name"] == "Test Auto"
    assert retrieved["workflow_filename"] == "studio_01_mcp_ticket_swarm.json"
    assert retrieved["active"] is True
    
    # List all
    autos = list_automations()
    assert any(a["id"] == auto_id for a in autos)
    
    # Delete it
    delete_automation(auto_id)
    assert get_automation(auto_id) is None


def test_api_endpoints():
    client = TestClient(app)
    
    # 1. Create a new automation via POST
    payload = {
        "name": "API Test Auto",
        "workflow_filename": "studio_01_mcp_ticket_swarm.json",
        "schedule_type": "cron",
        "cron_expression": "*/5 * * * *",
        "interval_mins": 5,
        "duration_mins": 60,
        "active": True,
        "author": "Shalini Barman Roy",
    }
    
    resp = client.post("/api/automations", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    auto_id = data["id"]
    assert auto_id.startswith("auto_")
    
    # 2. List all automations via GET
    list_resp = client.get("/api/automations")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert any(a["id"] == auto_id for a in list_data["automations"])
    
    # 3. Retrieve single via GET
    get_resp = client.get(f"/api/automations/{auto_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "API Test Auto"
    
    # 4. Trigger manually via POST
    run_resp = client.post(f"/api/automations/{auto_id}/run")
    assert run_resp.status_code == 200
    assert run_resp.json()["ok"] is True
    
    # 5. Delete via DELETE
    del_resp = client.delete(f"/api/automations/{auto_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["ok"] is True


def test_delete_run_db():
    import uuid
    from app.database import (
        append_automation_run,
        delete_automation_run,
        clear_automation_runs,
    )
    auto_id = f"test_del_db_{uuid.uuid4().hex[:6]}"
    save_automation(
        automation_id=auto_id,
        name="Delete Run Test",
        workflow_filename="studio_01_mcp_ticket_swarm.json",
        schedule_type="cron",
        cron_expression="*/5 * * * *",
        interval_mins=5,
        duration_mins=60,
        active=True,
        author="Shalini Barman Roy",
    )
    
    r1 = f"r1_{uuid.uuid4().hex[:6]}"
    r2 = f"r2_{uuid.uuid4().hex[:6]}"
    
    append_automation_run(r1, auto_id, "success", datetime.now(timezone.utc), 100, None)
    append_automation_run(r2, auto_id, "success", datetime.now(timezone.utc), 200, None)
    
    runs = list_automation_runs(auto_id)
    assert len(runs) == 2
    
    # Delete individual run
    delete_automation_run(auto_id, r1)
    runs = list_automation_runs(auto_id)
    assert len(runs) == 1
    assert runs[0]["run_id"] == r2
    
    # Clear all runs
    clear_automation_runs(auto_id)
    runs = list_automation_runs(auto_id)
    assert len(runs) == 0
    
    delete_automation(auto_id)


def test_delete_run_api():
    import uuid
    client = TestClient(app)
    
    # Create automation
    resp = client.post("/api/automations", json={
        "name": "Delete API Test Auto",
        "workflow_filename": "studio_01_mcp_ticket_swarm.json",
        "schedule_type": "cron",
        "cron_expression": "*/5 * * * *",
        "interval_mins": 5,
        "duration_mins": 60,
        "active": True,
        "author": "Shalini Barman Roy",
    })
    auto_id = resp.json()["id"]
    
    r1 = f"api_r1_{uuid.uuid4().hex[:6]}"
    r2 = f"api_r2_{uuid.uuid4().hex[:6]}"
    
    # Let runs propagate or mock runs in DB
    from app.database import append_automation_run
    append_automation_run(r1, auto_id, "success", datetime.now(timezone.utc), 100, None)
    append_automation_run(r2, auto_id, "success", datetime.now(timezone.utc), 200, None)
    
    # Get runs
    runs_resp = client.get(f"/api/automations/{auto_id}/runs")
    runs = runs_resp.json()["runs"]
    assert len(runs) >= 2
    
    # Delete individual run
    del_run_resp = client.delete(f"/api/automations/{auto_id}/runs/{r1}")
    assert del_run_resp.status_code == 200
    assert del_run_resp.json()["ok"] is True
    
    # Verify deleted
    runs = client.get(f"/api/automations/{auto_id}/runs").json()["runs"]
    assert not any(r["run_id"] == r1 for r in runs)
    
    # Clear all runs
    clear_runs_resp = client.delete(f"/api/automations/{auto_id}/runs")
    assert clear_runs_resp.status_code == 200
    assert clear_runs_resp.json()["ok"] is True
    
    # Verify cleared
    runs = client.get(f"/api/automations/{auto_id}/runs").json()["runs"]
    assert len(runs) == 0
    
    client.delete(f"/api/automations/{auto_id}")


def test_automation_run_download_url():
    import uuid
    client = TestClient(app)
    auto_id = f"test_dl_{uuid.uuid4().hex[:6]}"
    save_automation(
        automation_id=auto_id,
        name="Download URL Test",
        workflow_filename="studio_01_mcp_ticket_swarm.json",
        schedule_type="cron",
        cron_expression="*/5 * * * *",
        interval_mins=5,
        duration_mins=60,
        active=True,
        author="Shalini Barman Roy",
    )
    
    r1 = f"dl_r_{uuid.uuid4().hex[:6]}"
    expected_url = "/report/test_output.xlsx"
    
    from app.database import append_automation_run
    try:
        append_automation_run(
            run_id=r1,
            automation_id=auto_id,
            status="success",
            triggered_at=datetime.now(timezone.utc),
            duration_ms=150,
            error=None,
            download_url=expected_url
        )
    except TypeError:
        pytest.fail("append_automation_run does not support download_url argument yet.")
        
    runs = list_automation_runs(auto_id)
    assert len(runs) == 1
    assert runs[0]["download_url"] == expected_url
    
    # Check API returns it
    resp = client.get(f"/api/automations/{auto_id}/runs")
    api_runs = resp.json()["runs"]
    assert len(api_runs) == 1
    assert api_runs[0]["download_url"] == expected_url
    
    delete_automation(auto_id)


def test_apply_output_overrides():
    from app.scheduler import apply_output_overrides
    dag = {
        "nodes": [
            {
                "id": "node_1",
                "type": "excel_output",
                "config": {"filename": "revenue.xlsx"}
            }
        ]
    }
    
    # 1. Default (no pattern): suffix with run_id
    res1 = apply_output_overrides(dag, None, "run123", datetime(2026, 5, 24, 11, 0, 0))
    assert res1["nodes"][0]["config"]["filename"] == "revenue_run123.xlsx"
    
    # 2. Custom pattern with run_id
    res2 = apply_output_overrides(dag, "custom_{run_id}.xlsx", "run123", datetime(2026, 5, 24, 11, 0, 0))
    assert res2["nodes"][0]["config"]["filename"] == "custom_run123.xlsx"
    
    # 3. Custom pattern with timestamp
    res3 = apply_output_overrides(dag, "report_{timestamp}.xlsx", "run123", datetime(2026, 5, 24, 11, 0, 0))
    assert res3["nodes"][0]["config"]["filename"] == "report_20260524_110000.xlsx"



