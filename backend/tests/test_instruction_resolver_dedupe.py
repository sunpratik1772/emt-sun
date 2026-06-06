from __future__ import annotations

from pathlib import Path

from generation.harness.instruction_resolver import InstructionResolver


def test_instruction_resolver_dedupes_within_cycle(tmp_path: Path) -> None:
    rules = tmp_path / "AGENTS.md"
    rules.write_text("Use safe defaults.", encoding="utf-8")

    resolver = InstructionResolver(project_root=tmp_path)
    resolver.begin_cycle()
    first = resolver.resolve()
    second = resolver.resolve()

    assert len(first) == 1
    assert "Use safe defaults." in first[0]
    assert second == []


def test_instruction_resolver_resets_between_cycles(tmp_path: Path) -> None:
    rules = tmp_path / "AGENTS.md"
    rules.write_text("Rule A", encoding="utf-8")

    resolver = InstructionResolver(project_root=tmp_path)
    resolver.begin_cycle()
    _ = resolver.resolve()
    resolver.begin_cycle()
    again = resolver.resolve()

    assert len(again) == 1
    assert "Rule A" in again[0]
