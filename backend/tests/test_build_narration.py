"""Tests for question-aware build narration."""
from __future__ import annotations

from copilot.build_narration import (
    build_contextual_plan_steps,
    build_thinking_monologue,
    split_request_phrases,
)
from generation.harness.intent import classify
from tests.thinking_fake_adapter import ThinkingFakeAdapter


def test_split_request_phrases() -> None:
    parts = split_request_phrases(
        "Load leads.csv, filter high-risk rows, and export a CSV summary."
    )
    assert any("leads.csv" in p for p in parts)
    assert any("high-risk" in p for p in parts)
    assert any("export" in p.lower() for p in parts)


def test_contextual_plan_steps_emit_single_thinking_block(monkeypatch) -> None:
    monkeypatch.setattr("copilot.thinking_monologue.gemini_configured", lambda: True)
    intent = classify(
        "Load leads.csv, filter high-risk rows, and export a CSV summary.",
        known_datasets={"leads.csv"},
    )
    steps = build_contextual_plan_steps(
        "Load leads.csv, filter high-risk rows, and export a CSV summary.",
        intent,
        None,
        adapter=ThinkingFakeAdapter(),
    )
    assert len(steps) == 1
    assert steps[0]["label"] == "Thinking"
    assert (steps[0]["done"] or "").strip()
    assert "Drafting" in (steps[0]["done"] or "")


def test_thinking_monologue_no_harness_jargon(monkeypatch) -> None:
    monkeypatch.setattr("copilot.thinking_monologue.gemini_configured", lambda: True)
    intent = classify(
        "Load leads.csv, filter high-risk rows, and export a CSV summary.",
        known_datasets={"leads.csv"},
    )
    text = build_thinking_monologue(
        "Load leads.csv, filter high-risk rows, and export a CSV summary.",
        intent,
        None,
        adapter=ThinkingFakeAdapter(),
    )
    assert "csv_output" not in text
    assert "maps to" not in text.lower()


def test_thinking_monologue_improve_existing_workflow(monkeypatch) -> None:
    monkeypatch.setattr("copilot.thinking_monologue.gemini_configured", lambda: True)
    prompt = (
        'Improve "Join Comms Messages with HS Alerts and Rank" with validation, '
        "a branch for failures, and an Outlook summary when the run completes."
    )
    intent = classify(prompt, known_datasets={"comms_messages", "hs_alerts"})
    text = build_thinking_monologue(prompt, intent, None, adapter=ThinkingFakeAdapter())
    assert "Join Comms Messages with HS Alerts and Rank" in text
    assert "validation" in text.lower()
    assert "branch" in text.lower()
    assert "outlook" in text.lower()
    assert "rebuild" in text.lower()
    assert "pipeline should work" not in text.lower()
    assert "user wants" not in text.lower()


def test_thinking_monologue_hs_trades(monkeypatch) -> None:
    monkeypatch.setattr("copilot.thinking_monologue.gemini_configured", lambda: True)
    intent = classify("Load hs_trades and export flagged rows", known_datasets={"hs_trades"})
    text = build_thinking_monologue(
        "Load hs_trades and export flagged rows",
        intent,
        None,
        adapter=ThinkingFakeAdapter(),
    )
    lower = text.lower()
    assert "hs_trades" in lower
    assert "pipeline should work" not in lower
    assert "user wants" not in lower
    assert "drafting now." in lower
