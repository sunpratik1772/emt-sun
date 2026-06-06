"""Write rows to a CSV string (returned in the output payload)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..context import RunContext
from ..node_spec import _spec_from_yaml

_HERE = Path(__file__).parent
  
import csv
import io

from ..output_files import write_export_file


def _upstream_rows(incoming):
    for out in incoming.values():
        if not isinstance(out, dict):
            continue
        rows = out.get("rows")
        if isinstance(rows, list) and rows:
            return list(rows)
        resp = out.get("response")
        if isinstance(resp, str) and resp.strip():
            return [{"response": resp, "briefing": resp}]
    return []


def run(node: dict, ctx: RunContext, incoming: dict[str, Any]) -> dict[str, Any]:
    cfg = node.get("config") or {}
    filename = cfg.get("filename") or "output.csv"
    rows = _upstream_rows(incoming)
    if not rows:
        data = b""
        path, download_url = write_export_file(filename, data, default_name="output.csv")
        ctx.report_path = str(path)
        return {
            "filename": path.name,
            "rowCount": 0,
            "csv": "",
            "report_path": str(path),
            "download_url": download_url,
        }
    cols = list(rows[0].keys())
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow({c: r.get(c, "") for c in cols})
    text = buf.getvalue()
    data = text.encode("utf-8")
    path, download_url = write_export_file(filename, data, default_name="output.csv")
    ctx.report_path = str(path)
    return {
        "filename": path.name,
        "rowCount": len(rows),
        "csv": text,
        "byteSize": len(data),
        "rows": rows,
        "report_path": str(path),
        "download_url": download_url,
    }
  
NODE_SPEC = _spec_from_yaml(_HERE / "csv_output.yaml", run)
  