"""Streamed Studio runs must wire incoming-handler edges like sync /run."""
from __future__ import annotations

import json
from pathlib import Path

from engine.jobs import get_default_runner

_WORKFLOW = Path(__file__).resolve().parents[1] / "good_examples" / "studio_01_mcp_ticket_swarm.json"


def test_stream_excel_export_sets_download_url():
    wf = json.loads(_WORKFLOW.read_text())
    dag = {"nodes": wf["nodes"], "edges": wf["edges"]}
    export_out = None
    result = None
    for ev in get_default_runner().stream(dag, {}):
        if ev.get("type") == "node_complete" and ev.get("node_id") == "export":
            export_out = (ev.get("output") or {}).get("node_output") or {}
        if ev.get("type") == "workflow_complete":
            result = ev.get("result") or {}

    assert export_out, "export node should complete"
    assert export_out.get("rowsWritten", 0) > 0, export_out
    assert export_out.get("download_url"), export_out
    assert result.get("download_url"), result
    assert result.get("report_path")
