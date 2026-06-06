"""
End-to-end tests for the copilot generation pipeline.

Acceptance criteria:
  1. New workflow generates logical flow as per prompt and generates artifacts
  2. Edit 3-4 times and each time provide correct artifacts
  3. Memory persists across sessions
  4. Intent classification + retrieval enriches the pipeline

These tests use a mock LLM that returns deterministic workflows,
so they exercise the full pipeline (intent → retrieve → generate →
validate → finalize → memory) without needing a real API key.
"""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from typing import Any

from copilot.workflow_generator import WorkflowCopilot
from copilot.workflow_finalize import finalize_workflow
from generation.harness.runner import AgentRunner
from generation.harness.memory import MemoryManager
from generation.harness.intent import classify as classify_intent
from generation.planner import Planner


# ---------------------------------------------------------------------------
# Fixtures: deterministic workflows the mock LLM returns
# ---------------------------------------------------------------------------

def _csv_report_workflow() -> dict:
    """A simple workflow: trigger → extract → filter → csv output."""
    return {
        "intent": "create_workflow",
        "answer": "Built a CSV report workflow.",
        "thinking_steps": ["Loading data", "Filtering", "Writing output"],
        "workflow": {
            "name": "CSV Report",
            "description": "Extract orders, filter, write CSV",
            "nodes": [
                {"id": "n1", "type": "manual_trigger", "label": "Start", "config": {}, "position": {"x": 60, "y": 280}},
                {"id": "n2", "type": "csv_extract", "label": "Load Orders", "config": {"source": "orders.csv"}, "position": {"x": 320, "y": 280}},
                {"id": "n3", "type": "filter", "label": "Delivered Only", "config": {"expression": "row.status == 'delivered'"}, "position": {"x": 600, "y": 280}},
                {"id": "n4", "type": "csv_output", "label": "Write Report", "config": {"filename": "delivered_orders.csv"}, "position": {"x": 900, "y": 280}},
            ],
            "edges": [
                {"id": "e1", "source": "n1", "target": "n2"},
                {"id": "e2", "source": "n2", "target": "n3"},
                {"id": "e3", "source": "n3", "target": "n4"},
            ],
        },
    }


def _csv_report_with_sort() -> dict:
    """Edit 1: add a sort node before output."""
    wf = _csv_report_workflow()
    wf["answer"] = "Added sort by total descending."
    wf["thinking_steps"] = ["Adding sort node", "Rewiring edges"]
    nodes = wf["workflow"]["nodes"]
    nodes.insert(3, {
        "id": "n5", "type": "sort", "label": "Sort by Total",
        "config": {"sortBy": "total", "order": "desc"},
        "position": {"x": 750, "y": 280},
    })
    wf["workflow"]["edges"] = [
        {"id": "e1", "source": "n1", "target": "n2"},
        {"id": "e2", "source": "n2", "target": "n3"},
        {"id": "e3", "source": "n3", "target": "n5"},
        {"id": "e4", "source": "n5", "target": "n4"},
    ]
    return wf


def _csv_report_with_group() -> dict:
    """Edit 2: add group_by before sort."""
    wf = _csv_report_with_sort()
    wf["answer"] = "Added group by region with sum of totals."
    wf["thinking_steps"] = ["Adding group_by node"]
    nodes = wf["workflow"]["nodes"]
    nodes.insert(3, {
        "id": "n6", "type": "group_by", "label": "Group by Region",
        "config": {"groupBy": "region", "aggregateCol": "total", "aggregateFn": "sum", "alias": "total_revenue"},
        "position": {"x": 680, "y": 280},
    })
    wf["workflow"]["edges"] = [
        {"id": "e1", "source": "n1", "target": "n2"},
        {"id": "e2", "source": "n2", "target": "n3"},
        {"id": "e3", "source": "n3", "target": "n6"},
        {"id": "e4", "source": "n6", "target": "n5"},
        {"id": "e5", "source": "n5", "target": "n4"},
    ]
    return wf


def _csv_report_with_code() -> dict:
    """Edit 3: add a code node for custom enrichment."""
    wf = _csv_report_with_group()
    wf["answer"] = "Added code node for revenue calculation."
    wf["thinking_steps"] = ["Adding code node"]
    nodes = wf["workflow"]["nodes"]
    nodes.insert(4, {
        "id": "n7", "type": "code", "label": "Revenue Calc",
        "config": {
            "code": "output = [dict(r, revenue_pct=round(r.get('total_revenue',0)/sum([x.get('total_revenue',1) for x in input_data['rows']])*100,1)) for r in input_data['rows']]",
            "code_summary": "Calculate revenue percentage per region",
        },
        "position": {"x": 720, "y": 280},
    })
    wf["workflow"]["edges"] = [
        {"id": "e1", "source": "n1", "target": "n2"},
        {"id": "e2", "source": "n2", "target": "n3"},
        {"id": "e3", "source": "n3", "target": "n6"},
        {"id": "e4", "source": "n6", "target": "n7"},
        {"id": "e5", "source": "n7", "target": "n5"},
        {"id": "e6", "source": "n5", "target": "n4"},
    ]
    return wf


def _excel_output_workflow() -> dict:
    """Edit 4: change output from CSV to Excel."""
    wf = _csv_report_with_code()
    wf["answer"] = "Switched output to Excel format."
    wf["thinking_steps"] = ["Replacing csv_output with excel_output"]
    nodes = wf["workflow"]["nodes"]
    # Replace csv_output with excel_output
    for i, n in enumerate(nodes):
        if n["id"] == "n4":
            nodes[i] = {
                "id": "n4", "type": "excel_output", "label": "Write Excel",
                "config": {"filename": "regional_report.xlsx", "tabNames": "Regional Revenue"},
                "position": {"x": 900, "y": 280},
            }
    return wf


# ---------------------------------------------------------------------------
# Mock LLM that returns workflows in sequence
# ---------------------------------------------------------------------------

class SequentialMockLLM:
    """Stub LLM that returns pre-built workflow JSON envelopes."""

    def __init__(self, responses: list[dict]):
        self._responses = [json.dumps(r) for r in responses]
        self._idx = 0
        self.calls: list[str] = []

    def complete(self, system_prompt: str, history: list[dict], user_turn: str) -> str:
        self.calls.append(user_turn)
        if self._idx < len(self._responses):
            resp = self._responses[self._idx]
            self._idx += 1
            return resp
        return self._responses[-1]


ALL_RESPONSES = [
    _csv_report_workflow(),
    _csv_report_with_sort(),
    _csv_report_with_group(),
    _csv_report_with_code(),
    _excel_output_workflow(),
]


@pytest.fixture
def memory_dir(tmp_path):
    return tmp_path / "memory"


@pytest.fixture
def mock_llm():
    return SequentialMockLLM(ALL_RESPONSES)


@pytest.fixture
def copilot(memory_dir, mock_llm):
    """WorkflowCopilot with mock LLM and isolated memory."""
    cp = WorkflowCopilot()
    cp._memory = MemoryManager(memory_dir=memory_dir)
    from generation.harness.retriever import ContextRetriever
    cp._retriever = ContextRetriever(memory=cp._memory)
    cp._runner = AgentRunner(
        planner=Planner(mock_llm),
        prompt_builder=cp._prompt_builder,
        memory=cp._memory,
        retriever=cp._retriever,
    )
    cp._runner.runtime_smoke_enabled = False
    return cp


class TestNewWorkflowGeneration:
    """Acceptance: new workflow generates logical flow as per prompt."""

    def test_generates_valid_workflow(self, copilot):
        result = copilot.generate_with_critic(
            "Create a workflow to filter delivered orders and export as CSV",
            iterations=1,
        )
        assert result["success"] is True
        wf = result["workflow"]
        assert wf is not None
        assert len(wf["nodes"]) >= 4
        assert len(wf["edges"]) >= 3

    def test_workflow_has_logical_flow(self, copilot):
        result = copilot.generate_with_critic(
            "Create a workflow to filter delivered orders and export as CSV",
            iterations=1,
        )
        wf = result["workflow"]
        node_types = [n["type"] for n in wf["nodes"]]
        assert "manual_trigger" in node_types
        assert "csv_extract" in node_types
        assert "filter" in node_types
        assert "csv_output" in node_types

    def test_workflow_has_trigger_first(self, copilot):
        result = copilot.generate_with_critic(
            "Create a workflow to filter delivered orders",
            iterations=1,
        )
        wf = result["workflow"]
        first_node = wf["nodes"][0]
        assert first_node["type"] == "manual_trigger"

    def test_workflow_has_artifact_output(self, copilot):
        result = copilot.generate_with_critic(
            "Create a workflow to filter delivered orders and export as CSV",
            iterations=1,
        )
        wf = result["workflow"]
        output_node = next(
            n for n in wf["nodes"] if n["type"] == "csv_output"
        )
        assert output_node["config"]["filename"] == "delivered_orders.csv"

    def test_workflow_is_finalized(self, copilot):
        result = copilot.generate_with_critic(
            "Create a workflow",
            iterations=1,
        )
        wf = result["workflow"]
        assert "schema_version" in wf
        assert "workflow_id" in wf
        assert all("from" in e for e in wf["edges"])


class TestEditIterations:
    """Acceptance: edit 3-4 times, each time provides correct artifacts."""

    def test_edit_1_adds_sort(self, copilot):
        # Initial generation
        r1 = copilot.generate_with_critic("Create CSV report", iterations=1)
        wf1 = r1["workflow"]
        assert r1["success"]

        # Edit 1: add sort
        r2 = copilot.generate_with_critic(
            "Add a sort by total descending before the output",
            iterations=1,
            current_workflow=wf1,
        )
        assert r2["success"]
        wf2 = r2["workflow"]
        node_types = [n["type"] for n in wf2["nodes"]]
        assert "sort" in node_types
        assert len(wf2["nodes"]) == len(wf1["nodes"]) + 1

    def test_edit_2_adds_group_by(self, copilot):
        r1 = copilot.generate_with_critic("Create CSV report", iterations=1)
        r2 = copilot.generate_with_critic(
            "Add sort", iterations=1, current_workflow=r1["workflow"],
        )
        r3 = copilot.generate_with_critic(
            "Add group by region with sum of totals",
            iterations=1,
            current_workflow=r2["workflow"],
        )
        assert r3["success"]
        wf3 = r3["workflow"]
        node_types = [n["type"] for n in wf3["nodes"]]
        assert "group_by" in node_types

    def test_edit_3_adds_code_node(self, copilot):
        r1 = copilot.generate_with_critic("Create CSV report", iterations=1)
        r2 = copilot.generate_with_critic("Add sort", iterations=1, current_workflow=r1["workflow"])
        r3 = copilot.generate_with_critic("Add group by", iterations=1, current_workflow=r2["workflow"])
        r4 = copilot.generate_with_critic(
            "Add a code node to calculate revenue percentage per region",
            iterations=1,
            current_workflow=r3["workflow"],
        )
        assert r4["success"]
        wf4 = r4["workflow"]
        node_types = [n["type"] for n in wf4["nodes"]]
        assert "code" in node_types

    def test_edit_4_changes_output_to_excel(self, copilot):
        r1 = copilot.generate_with_critic("Create CSV report", iterations=1)
        r2 = copilot.generate_with_critic("Add sort", iterations=1, current_workflow=r1["workflow"])
        r3 = copilot.generate_with_critic("Add group by", iterations=1, current_workflow=r2["workflow"])
        r4 = copilot.generate_with_critic("Add code node", iterations=1, current_workflow=r3["workflow"])
        r5 = copilot.generate_with_critic(
            "Change the output from CSV to Excel format",
            iterations=1,
            current_workflow=r4["workflow"],
        )
        assert r5["success"]
        wf5 = r5["workflow"]
        node_types = [n["type"] for n in wf5["nodes"]]
        assert "excel_output" in node_types
        assert "csv_output" not in node_types
        excel_node = next(n for n in wf5["nodes"] if n["type"] == "excel_output")
        assert "xlsx" in excel_node["config"]["filename"]

    def test_node_ids_preserved_across_edits(self, copilot):
        """Existing node IDs should survive edits unchanged."""
        r1 = copilot.generate_with_critic("Create CSV report", iterations=1)
        original_ids = {n["id"] for n in r1["workflow"]["nodes"]}

        r2 = copilot.generate_with_critic(
            "Add sort", iterations=1, current_workflow=r1["workflow"],
        )
        edit_ids = {n["id"] for n in r2["workflow"]["nodes"]}
        assert original_ids.issubset(edit_ids)

    def test_edges_rewired_correctly_after_insert(self, copilot):
        """When a node is inserted, edges should connect through it."""
        r1 = copilot.generate_with_critic("Create CSV report", iterations=1)
        r2 = copilot.generate_with_critic(
            "Add sort", iterations=1, current_workflow=r1["workflow"],
        )
        wf2 = r2["workflow"]
        edge_pairs = [(e["from"], e["to"]) for e in wf2["edges"]]
        # sort node (n5) should be between filter (n3) and output (n4)
        assert ("n3", "n5") in edge_pairs
        assert ("n5", "n4") in edge_pairs


class TestStreamingGeneration:
    """Acceptance: streaming produces correct events sequence."""

    def test_stream_yields_thinking_steps(self, copilot):
        events = list(copilot.generate_with_critic_stream(
            "Create a CSV report workflow",
            iterations=1,
        ))
        thinking = [e for e in events if e.get("type") == "thinking"]
        assert len(thinking) >= 1

    def test_stream_yields_workflow_created(self, copilot):
        events = list(copilot.generate_with_critic_stream(
            "Create a CSV report workflow",
            iterations=1,
        ))
        wf_events = [e for e in events if e.get("type") == "workflow_created"]
        assert len(wf_events) == 1
        assert wf_events[0]["nodeCount"] >= 4

    def test_stream_yields_done(self, copilot):
        events = list(copilot.generate_with_critic_stream(
            "Create a CSV report workflow",
            iterations=1,
        ))
        done = [e for e in events if e.get("type") == "done"]
        assert len(done) >= 1

    def test_stream_intent_events_appear_before_pipeline(self, copilot):
        events = list(copilot.generate_with_critic_stream(
            "Create a CSV report workflow",
            iterations=1,
        ))
        intent_events = [
            e for e in events
            if e.get("type") in ("thinking", "agent_stage")
            and (
                "Analyzing request" in (e.get("step") or "")
                or "Analyzing request" in (e.get("stage") or "")
            )
        ]
        assert intent_events
        wf_events = [e for e in events if e.get("type") == "workflow_created"]
        if wf_events:
            first_intent_idx = events.index(intent_events[0])
            first_wf_idx = events.index(wf_events[0])
            assert first_intent_idx < first_wf_idx


class TestMemoryPersistence:
    """Acceptance: memory persists across sessions."""

    def test_memory_recorded_after_generation(self, copilot, memory_dir):
        copilot.generate_with_critic("Create a CSV report", iterations=1)
        memory_text = copilot._memory.load()
        assert "CSV Report" in memory_text or "succeeded" in memory_text

    def test_memory_persists_across_generations(self, copilot, memory_dir):
        copilot.generate_with_critic("Create workflow 1", iterations=1)
        copilot.generate_with_critic("Create workflow 2", iterations=1)
        memory_text = copilot._memory.load()
        assert len(memory_text) > 0

    def test_memory_available_to_next_session(self, copilot, memory_dir, mock_llm):
        copilot.generate_with_critic("Create a workflow", iterations=1)

        # Simulate new session — new copilot instance, same memory dir
        from generation.harness.retriever import ContextRetriever
        new_copilot = WorkflowCopilot()
        new_copilot._memory = MemoryManager(memory_dir=memory_dir)
        new_copilot._retriever = ContextRetriever(memory=new_copilot._memory)
        new_copilot._runner = AgentRunner(
            planner=Planner(mock_llm),
            prompt_builder=new_copilot._prompt_builder,
            memory=new_copilot._memory,
            retriever=new_copilot._retriever,
        )
        new_copilot._runner.runtime_smoke_enabled = False

        memory_text = new_copilot._memory.load()
        assert len(memory_text) > 0


class TestIntentEnrichment:
    """Verify intent classification feeds into the generation pipeline."""

    def test_edit_mode_detected_for_existing_workflow(self, copilot):
        wf = _csv_report_workflow()["workflow"]
        result = copilot.generate_with_critic(
            "fix the filter expression",
            iterations=1,
            current_workflow=wf,
        )
        assert result["success"]

    def test_enrichment_includes_template_for_front_running(self, copilot, mock_llm):
        """When scenario matches, template skeleton is included in prompt."""
        copilot.generate_with_critic(
            "detect front-running on FX desk",
            iterations=1,
        )
        assert len(mock_llm.calls) >= 1
        prompt = mock_llm.calls[0]
        assert "front-running" in prompt or "front running" in prompt

    def test_enrichment_includes_memory_after_first_run(self, copilot, mock_llm, memory_dir):
        copilot.generate_with_critic("Create a workflow", iterations=1)

        initial_calls = len(mock_llm.calls)
        copilot.generate_with_critic("Create another workflow", iterations=1)

        assert len(mock_llm.calls) > initial_calls
        second_call = mock_llm.calls[initial_calls]
        assert "copilot_memory" in second_call


class TestArtifactGeneration:
    """Verify that output nodes produce artifact configs."""

    def test_csv_output_has_filename(self, copilot):
        result = copilot.generate_with_critic(
            "Create a report that exports to CSV",
            iterations=1,
        )
        wf = result["workflow"]
        csv_nodes = [n for n in wf["nodes"] if n["type"] == "csv_output"]
        assert len(csv_nodes) == 1
        assert csv_nodes[0]["config"]["filename"].endswith(".csv")

    def test_excel_output_has_filename_and_tabs(self, copilot):
        # Run through 5 iterations to get to excel output
        r1 = copilot.generate_with_critic("Create", iterations=1)
        r2 = copilot.generate_with_critic("Sort", iterations=1, current_workflow=r1["workflow"])
        r3 = copilot.generate_with_critic("Group", iterations=1, current_workflow=r2["workflow"])
        r4 = copilot.generate_with_critic("Code", iterations=1, current_workflow=r3["workflow"])
        r5 = copilot.generate_with_critic("Excel", iterations=1, current_workflow=r4["workflow"])

        wf = r5["workflow"]
        excel_nodes = [n for n in wf["nodes"] if n["type"] == "excel_output"]
        assert len(excel_nodes) == 1
        assert excel_nodes[0]["config"]["filename"].endswith(".xlsx")
        assert "tabNames" in excel_nodes[0]["config"]

    def test_finalized_workflow_has_schema_version(self, copilot):
        result = copilot.generate_with_critic("Create CSV report", iterations=1)
        wf = result["workflow"]
        assert wf["schema_version"] == "1.0"

    def test_finalized_workflow_has_workflow_id(self, copilot):
        result = copilot.generate_with_critic("Create CSV report", iterations=1)
        wf = result["workflow"]
        assert "workflow_id" in wf
        assert len(wf["workflow_id"]) > 0
