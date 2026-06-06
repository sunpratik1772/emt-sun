from __future__ import annotations

from generation.prompt_builder import PromptBuilder


def test_prompt_contains_layer_slices() -> None:
    pb = PromptBuilder()
    prompt = pb.system_prompt("build a report")
    assert "## Provider overlay" in prompt
    assert "## Role overlay" in prompt
    assert "## Guardrail slice" in prompt
    assert "## Skill slice" in prompt


def test_last_step_snippet_present() -> None:
    pb = PromptBuilder()
    snippet = pb.last_step_snippet()
    assert "[FINAL STEP]" in snippet
