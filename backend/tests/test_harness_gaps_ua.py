"""Unit tests to verify Gap A (Ask Mode context), Gap B (parallel planning context), and Gap C (auto-sync triggers)."""
from __future__ import annotations

import os
import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from copilot.workflow_generator import WorkflowCopilot
from generation.harness.runner import AgentRunner
from generation.harness.intent import classify
from generation.harness.retriever import ContextRetriever, RetrievedContext
from generation.harness.state import AgentState
from app.routers.copilot import _autosave_draft


class TestGapA_AskModeContext:
    def test_format_chat_turn_injects_ua_context_when_enabled(self, monkeypatch):
        monkeypatch.setenv("DBSHERPA_ENABLE_UA_CONTEXT", "1")
        
        # Format turn with keywords matching Authentication domain
        msg = "how is session authentication handled in this project"
        formatted = WorkflowCopilot._format_chat_turn(msg)
        
        assert "[Understand-Anything Codebase Context]" in formatted
        assert "domain:auth" in formatted or "flow:auth:session" in formatted

    def test_format_chat_turn_excludes_ua_context_when_disabled(self, monkeypatch):
        monkeypatch.setenv("DBSHERPA_ENABLE_UA_CONTEXT", "0")
        
        msg = "how is session authentication handled in this project"
        formatted = WorkflowCopilot._format_chat_turn(msg)
        
        assert "[Understand-Anything Codebase Context]" not in formatted


class TestGapB_ParallelSubagentContext:
    @patch("generation.harness.runner.TaskManager")
    def test_parallel_task_dispatch_injects_ua_context(self, mock_task_manager, monkeypatch):
        monkeypatch.setenv("DBSHERPA_ENABLE_UA_CONTEXT", "1")
        
        # Setup mock task manager create_task
        mock_task_manager_instance = mock_task_manager.return_value
        mock_task_manager_instance.create_task = MagicMock()
        
        runner = AgentRunner(task_manager=mock_task_manager_instance)
        state = AgentState(scenario="Test scenario", max_attempts=3)
        state.profile = MagicMock()
        state.profile.permissions = {"task": True}
        
        from generation.harness.intent import Intent
        intent = Intent(
            mode="create",
            scenarios=("auth",),
            datasets=("orders.csv", "executions.csv"),
            actions=("filter", "group"),
            artifacts=("csv",),
            node_types=(),
            raw_scenario="auth profiles scheduler"
        )
        
        retrieved = runner.retriever.retrieve(intent)
        
        # Verify matched UA domains are present
        assert len(retrieved.ua_domains) > 0
        
        runner._dispatch_parallel_tasks(
            state,
            scenario="Test scenario",
            intent=intent,
            blueprint=None,
            planning_monologue="Test monologue",
            retrieved=retrieved
        )
        
        # Check that mock task creator was called and matched context was inside the prompt
        assert mock_task_manager_instance.create_task.call_count > 0
        _, kwargs = mock_task_manager_instance.create_task.call_args
        prompt = kwargs.get("prompt", "")
        
        assert "Relevant Architecture context:" in prompt
        assert "Domain: Authentication & Users" in prompt


class TestGapC_AutoSyncTriggers:
    @patch("app.routers.copilot.save_draft_db")
    @patch("app.routers.copilot._trigger_bg_refresh")
    def test_autosave_draft_triggers_bg_refresh(self, mock_refresh, mock_save):
        dag = {
            "name": "Test DAG",
            "workflow_id": "test-dag-123",
            "description": "Mock description",
            "nodes": [],
            "edges": []
        }
        
        # Run autosave
        res = _autosave_draft(dag)
        
        assert res is not None
        assert mock_save.call_count == 1
        assert mock_refresh.call_count == 1
