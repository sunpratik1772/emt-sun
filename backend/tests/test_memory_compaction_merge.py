from __future__ import annotations

from generation.harness.memory import MemoryManager


def test_memory_compaction_growth_bounded(tmp_path) -> None:
    memory = MemoryManager(memory_dir=tmp_path)
    for i in range(60):
        memory.observe(f"context item {i}", category="Recent Context")
        memory.observe(f"decision item {i}", category="Decisions")
    out = memory.compact()
    assert len(out) <= 2500
    assert out.count("context item") <= 5


def test_memory_dedupes_repeated_facts(tmp_path) -> None:
    memory = MemoryManager(memory_dir=tmp_path)
    for _ in range(5):
        memory.observe("same fact", category="Task Outputs")
    out = memory.compact()
    assert out.count("same fact") == 1
