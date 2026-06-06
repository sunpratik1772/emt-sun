"""csv_output writes a downloadable file under OUTPUT_DIR."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.dag_runner import run_workflow


@pytest.fixture()
def output_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DBSHERPA_OUTPUT_DIR", str(tmp_path))
    return tmp_path


def test_csv_output_sets_download_path(output_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    dag = {
        "nodes": [
            {"id": "start", "type": "manual_trigger", "config": {}},
            {
                "id": "load",
                "type": "csv_extract",
                "config": {"source": "orders.csv"},
            },
            {
                "id": "out",
                "type": "csv_output",
                "config": {"filename": "test_export.csv"},
            },
        ],
        "edges": [
            {"from": "start", "to": "load"},
            {"from": "load", "to": "out"},
        ],
    }
    ctx = run_workflow(dag, {})
    assert ctx.report_path
    path = Path(ctx.report_path)
    assert path.is_file()
    assert path.suffix == ".csv"
    out = ctx.output_map["out"]
    assert out["download_url"] == f"/report/{path.name}"
