"""End-to-end validation tests for Copilot generation with understand_anything context."""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from copilot.workflow_generator import WorkflowCopilot
from generation.harness.runner import AgentRunner
from generation.harness.memory import MemoryManager
from generation.harness.retriever import ContextRetriever
from generation.planner import Planner


class MockPlannerLLM:
    """Mock LLM to intercept the formatted user turn and return a valid draft."""
    def __init__(self):
        self.last_user_turn = None
        self.last_system_prompt = None

    def complete(self, system_prompt: str, history: list[dict], user_turn: str) -> str:
        self.last_system_prompt = system_prompt
        self.last_user_turn = user_turn
        # Return a simple mock workflow
        wf = {
            "name": "E2E UA Workflow",
            "description": "Auth execution flow verified",
            "nodes": [
                {"id": "n1", "type": "manual_trigger", "label": "Start", "config": {}},
                {"id": "n2", "type": "csv_output", "label": "Output", "config": {"filename": "out.csv"}}
            ],
            "edges": [
                {"from": "n1", "to": "n2"}
            ]
        }
        return json.dumps({
            "intent": "create_workflow",
            "answer": "Completed workflow generation with UA context.",
            "workflow": wf
        })


@pytest.fixture
def copilot(tmp_path):
    """WorkflowCopilot with isolated memory and our mock planner LLM."""
    mock_llm = MockPlannerLLM()
    cp = WorkflowCopilot()
    cp._memory = MemoryManager(memory_dir=tmp_path / "memory")
    cp._retriever = ContextRetriever(memory=cp._memory)
    cp._runner = AgentRunner(
        planner=Planner(mock_llm),
        prompt_builder=cp._prompt_builder,
        memory=cp._memory,
        retriever=cp._retriever,
    )
    cp._runner.runtime_smoke_enabled = False
    return cp, mock_llm


class TestE2EGenerationWithUA:
    def test_e2e_generation_injects_ua_context(self, copilot, monkeypatch):
        monkeypatch.setenv("DBSHERPA_ENABLE_UA_CONTEXT", "1")
        cp_instance, mock_llm = copilot

        # Run E2E generation with keywords matching Auth & Users domain
        result = cp_instance.generate_with_critic(
            "Create a workflow that does session management and auth profiles",
            iterations=1,
        )

        assert result["success"] is True
        assert result["workflow"]["name"] == "E2E UA Workflow"

        # Verify that context was matched and injected into the user turn
        assert mock_llm.last_user_turn is not None
        assert "<understand_anything_context>" in mock_llm.last_user_turn
        assert "Matching Domains:" in mock_llm.last_user_turn
        assert "domain:auth" in mock_llm.last_user_turn or "flow:auth:session" in mock_llm.last_user_turn

    def test_e2e_generation_excludes_ua_context_when_disabled(self, copilot, monkeypatch):
        monkeypatch.setenv("DBSHERPA_ENABLE_UA_CONTEXT", "0")
        cp_instance, mock_llm = copilot

        result = cp_instance.generate_with_critic(
            "Create a workflow that does session management and auth profiles",
            iterations=1,
        )

        assert result["success"] is True
        assert mock_llm.last_user_turn is not None
        assert "<understand_anything_context>" not in mock_llm.last_user_turn
