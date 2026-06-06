"""LLM thinking monologue generation."""
from __future__ import annotations

from copilot.thinking_monologue import (
    ThinkingMonologueContext,
    generate_thinking_monologue,
    iter_thinking_monologue_updates,
)
from tests.thinking_fake_adapter import ThinkingFakeAdapter


def test_generate_thinking_monologue_uses_llm(monkeypatch) -> None:
    monkeypatch.setattr("copilot.thinking_monologue.gemini_configured", lambda: True)
    ctx = ThinkingMonologueContext.for_ask("Improve join with validation")
    text = generate_thinking_monologue(ctx, adapter=ThinkingFakeAdapter())
    assert "validation" in text.lower()
    assert "Drafting" in text


def test_iter_thinking_monologue_updates_streams(monkeypatch) -> None:
    monkeypatch.setattr("copilot.thinking_monologue.gemini_configured", lambda: True)
    ctx = ThinkingMonologueContext.for_load("load orders pipeline", query="orders pipeline")
    updates = list(iter_thinking_monologue_updates(ctx, adapter=ThinkingFakeAdapter()))
    assert len(updates) >= 2
    assert "library" in updates[-1].lower() or "workflow" in updates[-1].lower()


class _LameAdapter:
    def single_shot(self, prompt, *, system_prompt=None, temperature=0.0, max_output_tokens=None):
        return "User wants export.\n2-step pipeline should work.\nDrafting now."

    def chat_turn_stream(self, *, system_prompt, history, user_turn, model=None, temperature=0.0, json_mode=True):
        yield from []


def test_lame_llm_output_rejected_uses_context_derived(monkeypatch) -> None:
    monkeypatch.setattr("copilot.thinking_monologue.gemini_configured", lambda: True)
    ctx = ThinkingMonologueContext.for_build(
        "export flagged rows",
        type("I", (), {"datasets": ("hs_trades",), "actions": ("export",)})(),
    )
    text = generate_thinking_monologue(ctx, adapter=_LameAdapter())
    assert "user wants" not in text.lower()
    assert "pipeline should work" not in text.lower()
    assert "hs_trades" in text.lower() or "Mapping" in text


def test_without_gemini_uses_context_derived(monkeypatch) -> None:
    monkeypatch.setattr("copilot.thinking_monologue.gemini_configured", lambda: False)

    def _boom(*args, **kwargs):
        raise RuntimeError("should not call LLM")

    monkeypatch.setattr("copilot.thinking_monologue.get_default_adapter", _boom)
    ctx = ThinkingMonologueContext.for_load("load orders", query="orders")
    text = generate_thinking_monologue(ctx)
    assert text.strip()
    assert "library" in text.lower() or "workflow" in text.lower()
    assert "user wants" not in text.lower()
    assert "pipeline should work" not in text.lower()
    updates = list(iter_thinking_monologue_updates(ctx))
    assert len(updates) == 1
    assert updates[0].strip()
