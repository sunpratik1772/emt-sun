#!/usr/bin/env python3
"""Run a demo_showcase workflow JSON (starts MCP bridge if needed)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

_BACKEND = Path(__file__).resolve().parent.parent
_SHOWCASE = _BACKEND / "workflows" / "demo_showcase"
_URL = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8765")


def _needs_mcp(dag: dict) -> bool:
    return any(n.get("type") == "mcp" for n in dag.get("nodes", []))


def _ensure_bridge() -> subprocess.Popen | None:
    try:
        if httpx.get(f"{_URL}/health", timeout=1.0).json().get("status") == "ok":
            return None
    except httpx.HTTPError:
        pass
    proc = subprocess.Popen(
        [sys.executable, "-m", "mcp_bridge.server"],
        cwd=str(_BACKEND),
        env={**os.environ, "MCP_BRIDGE_MODE": os.getenv("MCP_BRIDGE_MODE", "demo")},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(40):
        try:
            if httpx.get(f"{_URL}/health", timeout=0.5).json().get("status") == "ok":
                return proc
        except httpx.HTTPError:
            time.sleep(0.25)
    proc.kill()
    raise SystemExit("MCP bridge failed to start")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/run_demo_workflow.py <workflow.json|demo_01_...>")
        print("\nAvailable:")
        for p in sorted(_SHOWCASE.glob("demo_*.json")):
            print(f"  {p.name}")
        raise SystemExit(1)

    arg = sys.argv[1]
    path = Path(arg)
    if not path.is_file():
        path = _SHOWCASE / arg
        if not path.suffix:
            path = path.with_suffix(".json")
    if not path.is_file():
        raise SystemExit(f"Workflow not found: {arg}")

    load_dotenv(_BACKEND / ".env")
    os.environ.setdefault("MCP_SERVER_URL", _URL)
    sys.path.insert(0, str(_BACKEND))

    dag = json.loads(path.read_text())
    bridge = _ensure_bridge() if _needs_mcp(dag) else None
    try:
        from engine.copilot_validate import validate_dag_for_api
        from engine.dag_runner import run_workflow

        vr = validate_dag_for_api(dag)
        if not vr.valid:
            raise SystemExit(f"Validation failed: {vr.errors}")

        print(f"Running {path.name} …")
        ctx = run_workflow(dag, {})
        last = dag["nodes"][-1]["id"]
        out = ctx.output_map.get(last, {})
        print(json.dumps(out, indent=2)[:4000])
    finally:
        if bridge:
            bridge.terminate()


if __name__ == "__main__":
    main()
