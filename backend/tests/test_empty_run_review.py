"""Empty run_output — no redundant SQL, specific next-step on filter bottleneck."""
from __future__ import annotations

from copilot.next_action import (
    ensure_next_action_footer,
    infer_run_review_next_action,
    strip_suggested_sql_sections,
)
from copilot.run_verification import diagnose_empty_output, run_verification


def test_diagnose_empty_output_finds_filter_drop() -> None:
    wf = {
        "nodes": [
            {"id": "n01", "type": "db_query", "label": "Load alerts", "config": {"source": "hs_alerts"}},
            {"id": "n02", "type": "filter", "label": "Filter spoofing", "config": {"expression": 'row.keyword == "x"'}},
            {"id": "n03", "type": "csv_output", "label": "Export", "config": {}},
        ],
    }
    run_log = [
        {"node_id": "n01", "node_type": "db_query", "label": "Load alerts", "output": {"node_output": {"rowCount": 50}}},
        {"node_id": "n02", "node_type": "filter", "label": "Filter spoofing", "output": {"node_output": {"rowCount": 0}}},
        {"node_id": "n03", "node_type": "csv_output", "label": "Export", "output": {"node_output": {"rowCount": 0}}},
    ]
    d = diagnose_empty_output(wf, run_log)
    assert d is not None
    assert d["label"] == "Filter spoofing"
    assert d["node_type"] == "filter"
    assert "keyword" in (d.get("expression") or "")


def test_infer_run_review_next_action_empty_output_filter() -> None:
    verification = {
        "verification_summary": {"total_rows": 0},
        "output_row_count": 0,
        "empty_output_diagnosis": {
            "label": "Filter by Keyword",
            "node_type": "filter",
            "expression": 'row.display_post.includes("breach")',
        },
    }
    block = infer_run_review_next_action(
        {"name": "HS Alerts FX Spoofing Report", "nodes": []},
        verification,
        user_message="Summarize this workflow run.",
    )
    assert block is not None
    assert "Filter by Keyword" in block
    assert "Loosen" in block or "filter" in block.lower()
    assert "apply that change" in block.lower()
    assert "sample run" not in block.lower() or "Loosen" in block


def test_run_verification_attaches_diagnosis_when_empty() -> None:
    wf = {
        "name": "W",
        "nodes": [
            {"id": "n01", "type": "manual_trigger", "label": "Start", "config": {}},
            {"id": "n02", "type": "filter", "label": "Strict filter", "config": {"expression": "false"}},
        ],
    }
    run_log = [
        {"node_id": "n01", "node_type": "manual_trigger", "label": "Start", "output": {"node_output": {"rowCount": 1}}},
        {"node_id": "n02", "node_type": "filter", "label": "Strict filter", "output": {"node_output": {"rows": []}}},
    ]
    v = run_verification(wf, run_log, None, user_message="summarize")
    assert v.get("output_row_count") == 0
    assert v.get("empty_output_diagnosis") is not None


def test_strip_suggested_sql_and_replace_rerun_next_step() -> None:
    verification = {
        "verification_summary": {"total_rows": 0},
        "output_row_count": 0,
        "empty_output_diagnosis": {
            "label": "Publish Confluence Report",
            "node_type": "mcp",
        },
    }
    wf = {"name": "GitHub Activity Briefing Report", "nodes": []}
    llm_style = (
        "GitHub Activity Briefing Report Run Summary\n\n"
        "The final tabular output dataset for this run is empty.\n\n"
        "**Suggested SQL (run against this run's output)**\n"
        "The final tabular output dataset for this run is empty. However:\n\n"
        "```sql\n"
        "SELECT title, url, space\n"
        "FROM run_output\n"
        "WHERE node_id = 'n04';\n"
        "```\n\n"
        "**Next step:** Re-run GitHub Activity Briefing Report with sample data to confirm the output.\n\n"
        "Want me to help you adjust a step first?"
    )
    cleaned = strip_suggested_sql_sections(llm_style)
    assert "Suggested SQL" not in cleaned
    assert "SELECT title" not in cleaned

    out = ensure_next_action_footer(cleaned, workflow=wf, verification=verification)
    assert "Suggested SQL" not in out
    assert "sample run" not in out.lower()
    assert "Publish Confluence Report" in out or "adjust" in out.lower()
    assert "apply that change on the canvas" in out.lower()
