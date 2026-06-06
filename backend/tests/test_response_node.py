from __future__ import annotations

from engine.context import RunContext
from engine.nodes.response import handle_response


def test_response_node_builds_structured_payload() -> None:
    ctx = RunContext()
    ctx.report_path = "/tmp/out.xlsx"
    ctx.alert_payload = {"alert_id": "ALERT-FR-123"}
    ctx.set(
        "llm_summary_output",
        [
            {"tab_name": "order summary_ORD-1", "summary": "order summary text"},
            {"tab_name": "overall summary", "summary": "overall conclusion"},
            {"tab_name": "book A summary", "summary": "book narrative"},
        ],
    )
    node = {
        "id": "response",
        "type": "RESPONSE",
        "config": {
            "envelope_key": "response",
            "summary_input_key": "llm_summary_output",
            "summary_tab_field": "tab_name",
            "summary_text_field": "summary",
        },
    }

    handle_response(node, ctx)
    out = ctx.get("response_output", [])
    assert len(out) == 1
    payload = out[0]["response"]
    assert payload["artifact"] == "/tmp/out.xlsx"
    assert payload["alert_id"] == "ALERT-FR-123"
    assert payload["overall_summary"] == "overall conclusion"
    assert payload["order_summary"] == {"order summary_ORD-1": "order summary text"}
    assert set(payload["llm_summary"]) == {"order summary_ORD-1", "overall summary", "book A summary"}
