"""Tests for agent.harness.memory — OpenClaw-style memory.md with compaction."""
from __future__ import annotations

import pytest
from pathlib import Path
from generation.harness.memory import MemoryManager


@pytest.fixture
def memory(tmp_path):
    return MemoryManager(memory_dir=tmp_path)


class TestLoad:
    def test_empty_when_no_file(self, memory):
        assert memory.load() == ""

    def test_reads_existing_file(self, memory):
        memory.memory_path.write_text("# Copilot Memory\n\n## Recent Context\n- hello")
        assert "hello" in memory.load()

    def test_empty_for_whitespace_only(self, memory):
        memory.memory_path.write_text("   \n\n  ")
        assert memory.load() == ""


class TestObserve:
    def test_buffer_fact(self, memory):
        memory.observe("user prefers CSV", category="User Preferences")
        assert len(memory._buffer) == 1
        assert "[User Preferences]" in memory._buffer[0]

    def test_ignore_empty(self, memory):
        memory.observe("")
        memory.observe("   ")
        assert len(memory._buffer) == 0

    def test_buffer_capped(self, memory):
        for i in range(40):
            memory.observe(f"fact {i}")
        assert len(memory._buffer) == 30

    def test_observe_workflow_result_success(self, memory):
        memory.observe_workflow_result("test_wf", 5, True)
        assert any("succeeded" in f for f in memory._buffer)

    def test_observe_workflow_result_failure_with_errors(self, memory):
        errors = [{"code": "UNKNOWN_NODE_TYPE"}, {"code": "MISSING_EDGE"}]
        memory.observe_workflow_result("test_wf", 3, False, errors=errors)
        assert any("failed" in f for f in memory._buffer)
        assert any("UNKNOWN_NODE_TYPE" in f for f in memory._buffer)

    def test_observe_user_preference(self, memory):
        memory.observe_user_preference("prefers Excel output")
        assert any("User Preferences" in f for f in memory._buffer)

    def test_observe_edit_pattern(self, memory):
        memory.observe_edit_pattern("always adds CODE after MERGE")
        assert any("Workflow Patterns" in f for f in memory._buffer)


class TestCompact:
    def test_no_op_when_buffer_empty(self, memory):
        result = memory.compact()
        assert result == ""

    def test_deterministic_compact_creates_file(self, memory):
        memory.observe("first fact", category="Recent Context")
        result = memory.compact()
        assert memory.memory_path.exists()
        assert "first fact" in result

    def test_facts_land_in_correct_sections(self, memory):
        memory.observe("user likes CSV", category="User Preferences")
        memory.observe("always merges first", category="Workflow Patterns")
        memory.observe("fix: add output_name", category="Learned Fixes")
        memory.observe("ran 5-node workflow", category="Recent Context")
        result = memory.compact()
        lines = result.splitlines()
        pref_idx = next(i for i, l in enumerate(lines) if "User Preferences" in l)
        pattern_idx = next(i for i, l in enumerate(lines) if "Workflow Patterns" in l)
        fixes_idx = next(i for i, l in enumerate(lines) if "Learned Fixes" in l)
        recent_idx = next(i for i, l in enumerate(lines) if "Recent Context" in l)
        assert pref_idx < pattern_idx < fixes_idx < recent_idx

    def test_deduplication(self, memory):
        memory.observe("same fact", category="Recent Context")
        memory.observe("same fact", category="Recent Context")
        result = memory.compact()
        assert result.count("same fact") == 1

    def test_section_bounds(self, memory):
        for i in range(10):
            memory.observe(f"context {i}", category="Recent Context")
        result = memory.compact()
        assert result.count("- context") <= 5

    def test_truncation_at_max_chars(self, memory):
        for i in range(50):
            memory.observe(f"very long fact number {i} " * 5, category="User Preferences")
        result = memory.compact()
        assert len(result) <= 2500

    def test_incremental_compaction(self, memory):
        memory.observe("first session fact", category="Recent Context")
        memory.compact()
        memory.observe("second session fact", category="Recent Context")
        result = memory.compact()
        assert "first session fact" in result
        assert "second session fact" in result

    def test_llm_compact_fn_used_when_provided(self, memory):
        memory.observe("some fact")
        def fake_llm(old, new_facts):
            return "# LLM Compacted Memory\n\n- merged fact"
        result = memory.compact(llm_compact_fn=fake_llm)
        assert "LLM Compacted" in result

    def test_llm_compact_fn_fallback_on_error(self, memory):
        memory.observe("some fact")
        def bad_llm(old, new_facts):
            raise ValueError("LLM failed")
        result = memory.compact(llm_compact_fn=bad_llm)
        assert "some fact" in result


class TestClear:
    def test_clear_resets_state(self, memory):
        memory.observe("fact")
        memory.compact()
        memory.clear()
        assert len(memory._buffer) == 0
        content = memory.load()
        assert "# Copilot Memory" in content
        assert "fact" not in content


class TestFileLocking:
    def test_concurrent_writes_dont_corrupt(self, memory):
        """Basic check that two compactions don't interleave."""
        memory.observe("fact A")
        memory.compact()
        memory.observe("fact B")
        memory.compact()
        content = memory.load()
        assert "fact A" in content
        assert "fact B" in content


class TestMemoryFilter:
    def test_skips_template_placeholders(self, memory):
        memory.observe("Agent wrote {{row.company}} in rowTemplate")
        assert len(memory._buffer) == 0

    def test_skips_node_output_debug(self, memory):
        memory.observe('{"node_output": {"rows": [{"a": 1}]}}')
        assert len(memory._buffer) == 0

    def test_skips_markdown_table_dumps(self, memory):
        memory.observe("| col_a | col_b | col_c |\n| --- | --- | --- |\n| 1 | 2 | 3 |")
        assert len(memory._buffer) == 0

    def test_skips_enriched_row_stats(self, memory):
        memory.observe("Enriched 0/5 rows with poem field")
        assert len(memory._buffer) == 0

    def test_observe_turn_filters_debug(self, memory):
        memory.observe_turn('{"rows": [{"poem": "{{row.company}}"}]}')
        assert len(memory._buffer) == 0
        assert len(memory.runtime_recent_turns) == 0

    def test_note_task_output_filters_debug(self, memory):
        memory.note_task_output("columns: [alert_id, spread_pips]")
        assert len(memory._buffer) == 0

    def test_keeps_normal_facts(self, memory):
        memory.observe("User prefers Excel exports for surveillance bundles")
        assert len(memory._buffer) == 1

    def test_dedupes_identical_token_stats(self, memory):
        memory.note_token_stats(1000, 8000)
        memory.note_token_stats(1000, 8000)
        assert len(memory._buffer) == 1
