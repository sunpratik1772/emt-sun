#!/usr/bin/env python3
"""Run the three live MCP workflows in sequence (Confluence → Jira → GitHub)."""
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
_ROOT = _BACKEND.parent
_URL = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8765")


def _ensure_bridge() -> subprocess.Popen | None:
    try:
        if httpx.get(f"{_URL}/health", timeout=1.0).json().get("status") == "ok":
            return None
    except httpx.HTTPError:
        pass
    proc = subprocess.Popen(
        [sys.executable, "-m", "mcp_bridge.server"],
        cwd=str(_BACKEND),
        env={**os.environ, "MCP_BRIDGE_MODE": "live"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
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
    load_dotenv(_BACKEND / ".env")
    os.environ.setdefault("MCP_SERVER_URL", _URL)
    os.environ.setdefault("MCP_BRIDGE_MODE", "live")
    sys.path.insert(0, str(_BACKEND))
    os.chdir(_BACKEND)

    from engine.dag_runner import run_workflow

    bridge = _ensure_bridge()
    try:
        wf1 = json.loads(
            (_BACKEND / "workflows/mcp_integrations/live_01_studio_architecture_confluence.json").read_text()
        )
        ctx1 = run_workflow(wf1, {})
        pub = ctx1.output_map.get("publish_doc", {})
        rows1 = pub.get("rows") or []
        if not rows1:
            raise SystemExit(f"WF1 failed: {pub}")
        page_id = rows1[0]["page_id"]
        print("WF1 Confluence page:", rows1[0].get("url"), "page_id=", page_id)

        wf2 = json.loads(
            (_BACKEND / "workflows/mcp_integrations/live_02_confluence_to_jira.json").read_text()
        )
        for n in wf2["nodes"]:
            if n["id"] == "create_jira":
                n["config"]["params"] = {"page_id": page_id}
        ctx2 = run_workflow(wf2, {})
        jira_out = ctx2.output_map.get("create_jira", {})
        jira_rows = jira_out.get("rows") or []
        if len(jira_rows) < 1:
            raise SystemExit(f"WF2 failed: {jira_out}")
        for r in jira_rows:
            print("WF2 Jira:", r.get("issue_key"), r.get("url"))

        wf3 = json.loads(
            (_BACKEND / "workflows/mcp_integrations/live_03_jira_to_github.json").read_text()
        )
        wf3["nodes"] = [n for n in wf3["nodes"] if n["id"] not in ("load_jira",)]
        wf3["edges"] = [{"from": "start", "to": "github_fix"}, {"from": "github_fix", "to": "export"}]
        for n in wf3["nodes"]:
            if n["id"] == "github_fix":
                n["config"]["params"] = {"max": 2, "data": jira_rows}
        ctx3 = run_workflow(wf3, {})
        gh_out = ctx3.output_map.get("github_fix", {})
        for r in gh_out.get("rows") or []:
            print("WF3 GitHub PR:", r.get("pr_url"))
    finally:
        if bridge:
            bridge.terminate()


if __name__ == "__main__":
    main()
