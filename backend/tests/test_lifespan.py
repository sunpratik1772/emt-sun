import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

@pytest.fixture(autouse=True)
def disable_mcp_autostart():
    with patch.dict(os.environ, {"MCP_BRIDGE_AUTOSTART": "0"}):
        yield

def test_server_lifespan_starts_and_stops_scheduler():
    from server import app
    from app import scheduler
    
    # Initially the scheduler task should not be running/spawned in this test run
    assert scheduler._scheduler_task is None
    
    # Start the test client which triggers the FastAPI lifespan
    with TestClient(app) as client:
        # Check that the scheduler task is successfully spawned
        assert scheduler._scheduler_task is not None
        assert not scheduler._scheduler_task.cancelled()
        
    # After exiting the context, the scheduler task should be stopped/cancelled
    assert scheduler._scheduler_task is None
