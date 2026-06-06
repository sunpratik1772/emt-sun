"""Tests for agent.harness.retriever — context retrieval for generation."""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from generation.harness.intent import classify
from generation.harness.memory import MemoryManager
from generation.harness.retriever import ContextRetriever, RetrievedContext


@pytest.fixture
def templates_dir(tmp_path):
    """Create a temporary templates directory with test templates."""
    tmpl = {
        "name": "fx_front_running",
        "description": "Front-running detection for FX",
        "matches": {
            "scenarios": ["front-running", "fro"],
            "datasets": ["orders", "executions"],
            "semantics": ["trader", "time"],
        },
        "parameters": [
            {"name": "trader_id", "type": "string", "required": True},
        ],
        "skeleton": {
            "name": "FX Front Running",
            "nodes": [{"id": "n01", "type": "MANUAL_TRIGGER", "label": "Start", "config": {}}],
            "edges": [],
        },
    }
    (tmp_path / "fx_front_running.json").write_text(json.dumps(tmpl))

    tmpl2 = {
        "name": "fi_spoof_layering",
        "description": "Spoofing/layering detection",
        "matches": {
            "scenarios": ["spoofing", "layering"],
            "datasets": ["orders"],
            "semantics": ["price"],
        },
        "parameters": [],
        "skeleton": {
            "name": "FI Spoofing",
            "nodes": [{"id": "n01", "type": "MANUAL_TRIGGER", "label": "Start", "config": {}}],
            "edges": [],
        },
    }
    (tmp_path / "fi_spoof_layering.json").write_text(json.dumps(tmpl2))
    return tmp_path


@pytest.fixture
def retriever(tmp_path, templates_dir):
    memory = MemoryManager(memory_dir=tmp_path / "memory")
    return ContextRetriever(memory=memory, templates_dir=templates_dir)


class TestTemplateRetrieval:
    def test_matches_template_for_front_running(self, retriever):
        intent = classify("detect front-running on FX desk")
        ctx = retriever.retrieve(intent)
        assert ctx.template_name == "fx_front_running"
        assert ctx.template_skeleton is not None
        assert len(ctx.template_parameters) == 1

    def test_matches_spoofing_template(self, retriever):
        intent = classify("build spoofing detection workflow")
        ctx = retriever.retrieve(intent)
        assert ctx.template_name == "fi_spoof_layering"

    def test_no_template_for_generic(self, retriever):
        intent = classify("merge two CSV files")
        ctx = retriever.retrieve(intent)
        assert ctx.template_name is None
        assert ctx.template_skeleton is None

    def test_no_template_in_edit_mode(self, retriever):
        intent = classify("fix the nodes", current_workflow={"nodes": [], "edges": []})
        ctx = retriever.retrieve(intent)
        assert ctx.template_name is None


class TestExampleLoading:
    def test_loads_examples_excluding_selected_template(self, retriever):
        intent = classify("detect front-running on FX desk")
        ctx = retriever.retrieve(intent)
        example_names = [e["name"] for e in ctx.example_workflows]
        assert ctx.template_name not in example_names

    def test_loads_at_most_two_examples(self, retriever):
        intent = classify("detect front-running")
        ctx = retriever.retrieve(intent)
        assert len(ctx.example_workflows) <= 2

    def test_examples_have_required_fields(self, retriever):
        intent = classify("detect spoofing patterns")
        ctx = retriever.retrieve(intent)
        for ex in ctx.example_workflows:
            assert "name" in ex
            assert "skeleton" in ex
            assert "relevance" in ex


class TestMemoryIntegration:
    def test_memory_loaded_into_context(self, retriever):
        retriever.memory.observe("user prefers CSV output", category="User Preferences")
        retriever.memory.compact()
        intent = classify("build a workflow")
        ctx = retriever.retrieve(intent)
        assert "CSV" in ctx.memory_text

    def test_empty_memory_is_empty_string(self, retriever):
        intent = classify("build a workflow")
        ctx = retriever.retrieve(intent)
        assert ctx.memory_text == ""


class TestContextSerialization:
    def test_to_dict(self, retriever):
        intent = classify("detect front-running")
        ctx = retriever.retrieve(intent)
        d = ctx.to_dict()
        assert "intent" in d
        assert "matched_skills" in d
        assert "has_template" in d
        assert "example_count" in d
        assert isinstance(d["has_memory"], bool)
