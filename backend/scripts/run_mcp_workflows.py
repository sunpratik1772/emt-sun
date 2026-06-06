#!/usr/bin/env python3
"""Run all MCP integration workflows (starts bridge if needed)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

_BACKEND = Path(__file__).resolve().parent.parent
_WORKFLOWS = _BACKEND / "workflows" / "mcp_integrations"
_URL = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8765")


def _ensure_bridge() -> subprocess.Popen | None:
    try:
        if httpx.get(f"{_URL}/health", timeout=1.0).status_code == 200:
            return None
    except httpx.HTTPError:
        pass
    env = {**os.environ, "MCP_BRIDGE_MODE": "demo", "MCP_BRIDGE_PORT": "8765"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "mcp_bridge.server"],
        cwd=str(_BACKEND),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(40):
        try:
            if httpx.get(f"{_URL}/health", timeout=0.5).status_code == 200:
                return proc
        except httpx.HTTPError:
            time.sleep(0.25)
    proc.kill()
    raise SystemExit("MCP bridge failed to start")


def _workflow_paths() -> list[Path]:
    """Demo MCP trio by default; pass --live for live_* (needs .env + run_live_mcp_chain.py)."""
    if "--live" in sys.argv:
        return sorted(_WORKFLOWS.glob("live_*.json"))
    return sorted(_WORKFLOWS.glob("[0-9][0-9]_*.json"))


def main() -> None:
    os.chdir(_BACKEND)
    sys.path.insert(0, str(_BACKEND))
    os.environ["MCP_SERVER_URL"] = _URL

    from engine.dag_runner import run_workflow

    paths = _workflow_paths()
    if not paths:
        raise SystemExit(f"No workflows matched in {_WORKFLOWS}")

    bridge = _ensure_bridge()
    failed = []
    try:
        for path in paths:
            dag = json.loads(path.read_text())
            try:
                ctx = run_workflow(dag, {})
                last = dag["nodes"][-1]["id"]
                out = ctx.output_map.get(last, {})
                print(f"\n=== {path.name} OK ===")
                print(json.dumps(out, indent=2)[:2000])
            except Exception as exc:
                failed.append((path.name, exc))
                print(f"\n=== {path.name} FAILED ===\n{exc}")
    finally:
        if bridge:
            bridge.terminate()
    if failed:
        raise SystemExit(f"{len(failed)} workflow(s) failed")


if __name__ == "__main__":
    main()
