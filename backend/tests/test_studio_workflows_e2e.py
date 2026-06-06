"""
End-to-end execution of all Studio demo workflows in good_examples/.

Definition of done for backend refactor: every studio_*.json validates,
executes through the DAG runner, and workflows with agent nodes run against
live Gemini when GEMINI_API_KEY is configured.
"""
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
_GOOD_EXAMPLES = _BACKEND / "good_examples"
_STUDIO_WORKFLOWS = sorted(_GOOD_EXAMPLES.glob("studio_*.json"))
_MCP_PORT = "8769"
_MCP_URL = f"http://127.0.0.1:{_MCP_PORT}"


@pytest.fixture(autouse=True)
def _studio_integration_env(monkeypatch):
    """Studio demos that hit external integrations use safe test endpoints."""
    if not os.environ.get("TEAMS_INCOMING_WEBHOOK_URL"):
        monkeypatch.setenv("TEAMS_INCOMING_WEBHOOK_URL", "https://httpbin.org/post")


def _gemini_configured() -> bool:
    key = os.environ.get("GEMINI_API_KEY", "")
    return bool(key) and key != "mock_key_for_testing"


from engine.mcp_nodes import workflow_uses_mcp


def _workflow_uses_agent(dag: dict) -> bool:
    return any(n.get("type") == "agent" for n in dag.get("nodes", []))


def _terminal_output(ctx, dag: dict) -> dict:
    nodes = dag.get("nodes") or []
    if not nodes:
        return {}
    last_id = nodes[-1]["id"]
    return ctx.output_map.get(last_id) or {}


@pytest.fixture(scope="module")
def mcp_bridge():
    """Demo MCP bridge for studio workflows that include MCP nodes."""
    url = _MCP_URL
    try:
        if httpx.get(f"{url}/health", timeout=1.0).status_code == 200:
            yield url
            return
    except httpx.HTTPError:
        pass

    env = os.environ.copy()
    env["MCP_BRIDGE_MODE"] = "demo"
    env["MCP_BRIDGE_PORT"] = _MCP_PORT
    proc = subprocess.Popen(
        [sys.executable, "-m", "mcp_bridge.server"],
        cwd=str(_BACKEND),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(40):
        try:
            if httpx.get(f"{url}/health", timeout=0.5).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.25)
    else:
        proc.kill()
        pytest.fail("MCP bridge failed to start for studio workflow tests")

    prev = os.environ.get("MCP_SERVER_URL")
    os.environ["MCP_SERVER_URL"] = url
    yield url
    proc.terminate()
    proc.wait(timeout=5)
    if prev is None:
        os.environ.pop("MCP_SERVER_URL", None)
    else:
        os.environ["MCP_SERVER_URL"] = prev


@pytest.mark.parametrize("path", _STUDIO_WORKFLOWS, ids=lambda p: p.name)
def test_studio_workflow_validates(path: Path) -> None:
    dag = json.loads(path.read_text())
    assert dag.get("tags") == ["studio_demo"], f"{path.name} missing studio_demo tag"
    result = validate_dag_for_api(dag)
    assert result.valid, [e.message for e in result.errors]


@pytest.mark.parametrize("path", _STUDIO_WORKFLOWS, ids=lambda p: p.name)
def test_studio_workflow_executes(path: Path, mcp_bridge: str) -> None:
    dag = json.loads(path.read_text())
    if _workflow_uses_agent(dag) and not _gemini_configured():
        pytest.skip(f"{path.name} has agent nodes — requires live GEMINI_API_KEY")

    if workflow_uses_mcp(dag):
        os.environ["MCP_SERVER_URL"] = mcp_bridge

    ctx = run_workflow(dag, {})
    out = _terminal_output(ctx, dag)
    assert out is not None
    if out.get("rowCount") is not None:
        assert out["rowCount"] >= 0
    elif "rows" in out:
        assert isinstance(out["rows"], list)
    elif "response" in out or "content" in out:
        assert out.get("response") is not None or out.get("content") is not None
    else:
        assert out, f"{path.name}: terminal node produced empty output"
