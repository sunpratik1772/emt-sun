"""Sherpa route parity — every path gets thinking monologue helpers + Next step footers."""
from __future__ import annotations

from copilot.build_narration import (
    build_ask_thinking_monologue,
    build_automate_thinking_monologue,
    build_failure_thinking_monologue,
    build_load_thinking_monologue,
)
from copilot.next_action import (
    ensure_ask_next_action_footer,
    ensure_automate_next_action_footer,
    ensure_failure_next_action_footer,
    ensure_load_next_action_footer,
)
from tests.thinking_fake_adapter import ThinkingFakeAdapter


def test_ask_monologue_and_footer(monkeypatch) -> None:
    monkeypatch.setattr("copilot.thinking_monologue.gemini_configured", lambda: True)
    mono = build_ask_thinking_monologue(
        "Why did the join fail?",
        recent_errors=[{"message": "x"}],
        adapter=ThinkingFakeAdapter(),
    )
    assert "Examining" in mono or "Tracing" in mono
    assert "errors" in mono.lower() or "join" in mono.lower()

    out = ensure_ask_next_action_footer("The join dropped rows.", user_message="Why did the join fail?")
    assert "**Next step:**" in out
    assert out.endswith("?")


def test_load_monologue_and_footer(monkeypatch) -> None:
    monkeypatch.setattr("copilot.thinking_monologue.gemini_configured", lambda: True)
    mono = build_load_thinking_monologue(
        "load orders pipeline",
        query="orders pipeline",
        adapter=ThinkingFakeAdapter(),
    )
    assert "library" in mono.lower() or "workflow" in mono.lower()

    out = ensure_load_next_action_footer(
        "Loaded **Orders** onto the canvas.",
        query="orders",
        loaded_name="Orders",
        found=True,
    )
    assert "**Next step:**" in out
    assert "sample run" in out.lower()


def test_automate_monologue_and_footer(monkeypatch) -> None:
    monkeypatch.setattr("copilot.thinking_monologue.gemini_configured", lambda: True)
    mono = build_automate_thinking_monologue(
        "Run daily at 9am",
        workflow={"name": "Orders Export"},
        build_first=False,
        adapter=ThinkingFakeAdapter(),
    )
    assert "automate" in mono.lower() or "schedule" in mono.lower() or "daily" in mono.lower()

    out = ensure_automate_next_action_footer(
        "Done — scheduled.",
        automation_name="Orders Export Automation",
        schedule_summary="Daily at 9:00 AM",
    )
    assert "**Next step:**" in out
    assert "Automations" in out


def test_failure_monologue_and_footer(monkeypatch) -> None:
    monkeypatch.setattr("copilot.thinking_monologue.gemini_configured", lambda: True)
    payload = {
        "user_request": "export leads",
        "validation_errors": [{"message": "missing source"}],
    }
    mono = build_failure_thinking_monologue("export leads", payload, adapter=ThinkingFakeAdapter())
    assert "validation" in mono.lower() or "trace" in mono.lower() or "recovery" in mono.lower()

    out = ensure_failure_next_action_footer("Build failed.", user_request="export leads", payload=payload)
    assert "**Next step:**" in out
    assert "regenerate" in out.lower() or "retry" in out.lower()
