from __future__ import annotations

from copilot.run_analyst import _deterministic_failure_summary, _failure_context_payload


def test_failure_summary_falls_back_when_llm_stream_empty(monkeypatch) -> None:
    from copilot import run_analyst as mod

    class EmptyStreamAdapter:
        def chat_turn_stream(self, **_kwargs):
            return iter([])

    monkeypatch.setattr(mod, "gemini_configured", lambda: True)
    monkeypatch.setattr(mod, "get_default_adapter", lambda: EmptyStreamAdapter())

    chunks = list(mod.stream_generation_failure_summary(
        "Monitor comms_messages for urgent keyword and email analyst",
        errors=[{"code": "RUNTIME_SMOKE_FAILED", "message": "Runtime smoke test failed: missing outlook creds"}],
        runtime_smoke_error="missing outlook creds",
    ))
    text = "".join(chunks)
    assert "I understood your goal" in text
    assert "Recovery path" in text


def test_failure_payload_includes_errors_and_catalog() -> None:
    payload = _failure_context_payload(
        "Monitor comms for urgent keyword and email analyst",
        errors=[{
            "code": "MISSING_REQUIRED_PARAM",
            "message": "Node 'n4' (outlook) is missing required config field 'to'",
            "node_id": "n4",
            "field": "config.to",
        }],
        workflow={
            "name": "Urgent comms alert",
            "nodes": [
                {"id": "n1", "type": "manual_trigger", "label": "Start", "config": {}},
                {"id": "n4", "type": "outlook", "label": "Email analyst", "config": {}},
            ],
            "edges": [],
        },
        runtime_smoke_error="Outlook credentials missing",
        auto_fixes_applied=["condition: set sourceHandle true/false on branch edges"],
        attempts=3,
    )
    text = _deterministic_failure_summary(payload)
    assert "I understood your goal" in text
    assert "What went wrong" in text
    assert "outlook" in text.lower()
    assert "Recovery path" in text
    assert "Outlook credentials missing" in text
    assert "Draft walkthrough" in text
