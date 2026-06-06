"""Run MCP integration workflows against the local MCP bridge."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from engine.copilot_validate import validate_dag_for_api
from engine.dag_runner import run_workflow

_BACKEND = Path(__file__).resolve().parent.parent
_WORKFLOWS = _BACKEND / "workflows" / "mcp_integrations"
_BRIDGE_URL = "http://127.0.0.1:8768"


def _load(name: str) -> dict:
    path = _WORKFLOWS / name
    return json.loads(path.read_text())


@pytest.fixture(scope="module")
def mcp_bridge():
    """Start MCP bridge if not already listening."""
    try:
        r = httpx.get(f"{_BRIDGE_URL.rstrip('/')}/health", timeout=1.0)
        if r.status_code == 200:
            yield _BRIDGE_URL
            return
    except httpx.HTTPError:
        pass

    env = os.environ.copy()
    env["MCP_BRIDGE_MODE"] = "demo"
    env["MCP_BRIDGE_PORT"] = "8768"
    proc = subprocess.Popen(
        [sys.executable, "-m", "mcp_bridge.server"],
        cwd=str(_BACKEND),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(40):
        try:
            r = httpx.get(f"{_BRIDGE_URL.rstrip('/')}/health", timeout=0.5)
            if r.status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.25)
    else:
        proc.kill()
        pytest.fail("MCP bridge did not start")

    os.environ["MCP_SERVER_URL"] = _BRIDGE_URL
    yield _BRIDGE_URL
    proc.terminate()
    proc.wait(timeout=5)


@pytest.mark.parametrize(
    "workflow_file,min_rows",
    [
        ("01_confluence_to_tasks.json", 1),
        ("02_confluence_to_jira.json", 1),
        ("03_jira_to_github_fixes.json", 1),
    ],
)
def test_mcp_workflow_runs(workflow_file: str, min_rows: int, mcp_bridge: str) -> None:
    dag = _load(workflow_file)
    result = validate_dag_for_api(dag)
    assert result.valid, result.errors

    ctx = run_workflow(dag, {})

    # Last node should have produced rows or a rowCount
    last_id = dag["nodes"][-1]["id"]
    out = ctx.output_map.get(last_id, {})
    rows = out.get("rows") if isinstance(out, dict) else None
    if not rows:
        # csv_output may only expose rowCount
        assert int(out.get("rowCount", 0)) >= min_rows, out
    else:
        assert len(rows) >= min_rows, out
