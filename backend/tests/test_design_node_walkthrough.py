"""Per-node design walkthrough lines."""
from __future__ import annotations

from copilot.build_narration import design_node_walkthrough_lines, explain_node_line


def test_explain_node_lines_include_type_values_and_why() -> None:
    workflow = {
        "nodes": [
            {"id": "n1", "type": "manual_trigger", "label": "Start", "config": {}},
            {"id": "n2", "type": "csv_extract", "label": "Load Leads", "config": {"source": "leads.csv"}},
            {"id": "n3", "type": "filter", "label": "High-risk filter", "config": {"expression": "row.score >= 80"}},
            {"id": "n4", "type": "csv_output", "label": "Export", "config": {"filename": "high_risk_leads_summary.csv"}},
        ],
    }
    prompt = "Load leads.csv, filter high-risk rows, and export a CSV summary."
    lines = design_node_walkthrough_lines(prompt, workflow)
    assert len(lines) == 3
    joined = "\n".join(lines).lower()
    assert "csv extract" in joined
    assert "leads.csv" in joined
    assert "filter" in joined
    assert "row.score >= 80" in joined
    assert "high-risk" in joined
    assert "csv export" in joined
    assert "high_risk_leads_summary.csv" in joined


def test_explain_sort_node() -> None:
    node = {"id": "n3", "type": "sort", "label": "Sort by score", "config": {"sortBy": "score", "order": "desc"}}
    text = explain_node_line(node, "Sort leads.csv by score descending")
    assert "Sort" in text
    assert "`score`" in text
    assert "desc" in text
