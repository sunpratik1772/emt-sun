"""Tests for engine.response_formatters — data-driven agent response registry."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from engine.response_formatters import get_agent_response, _REGISTRY


@pytest.fixture
def mock_ctx():
    ctx = MagicMock()
    ctx.get.return_value = None
    return ctx


class TestRegistry:
    def test_all_expected_types_registered(self):
        expected = {
            "LLM_PLANNER", "PLAN_VALIDATOR", "LLM_ACTION", "ACTION_VALIDATOR",
            "GUARDRAIL", "TOOL_EXECUTOR", "LLM_CRITIC", "STATE_MANAGER",
            "LLM_EVALUATOR", "LOOP_CONTROLLER", "LLM_SYNTHESIZER",
            "LLM_CONTEXTUALIZER", "AGGREGATOR_NODE", "DATA_REDUCER",
            "ERROR_HANDLER",
        }
        assert expected.issubset(set(_REGISTRY.keys()))

    def test_unknown_type_returns_none(self, mock_ctx):
        node = {"type": "TOTALLY_FAKE_NODE", "config": {}}
        assert get_agent_response(node, {}, mock_ctx) is None


class TestPlannerFormatter:
    def test_with_steps(self, mock_ctx):
        node = {"type": "LLM_PLANNER", "config": {}}
        new_values = {"plan": {"steps": [{"action": "query_db"}, {"action": "filter"}]}}
        result = get_agent_response(node, new_values, mock_ctx)
        assert "2 step" in result
        assert "query_db" in result

    def test_empty_plan(self, mock_ctx):
        node = {"type": "LLM_PLANNER", "config": {}}
        new_values = {"plan": {}}
        result = get_agent_response(node, new_values, mock_ctx)
        assert "investigation plan" in result.lower()


class TestToolExecutorFormatter:
    def test_with_result_dict(self, mock_ctx):
        node = {"type": "TOOL_EXECUTOR", "config": {}}
        new_values = {"last_result": {"status": "success", "rows": 42}}
        result = get_agent_response(node, new_values, mock_ctx)
        assert "success" in result
        assert "42" in result

    def test_with_no_result(self, mock_ctx):
        node = {"type": "TOOL_EXECUTOR", "config": {}}
        result = get_agent_response(node, {}, mock_ctx)
        assert "Executed" in result


class TestCriticFormatter:
    def test_accepted(self, mock_ctx):
        node = {"type": "LLM_CRITIC", "config": {}}
        new_values = {"validation": {"valid": True, "confidence": 0.95}}
        result = get_agent_response(node, new_values, mock_ctx)
        assert "accepted" in result
        assert "0.95" in result

    def test_rejected_with_issues(self, mock_ctx):
        node = {"type": "LLM_CRITIC", "config": {}}
        new_values = {"validation": {
            "valid": False,
            "issues": ["missing trader_id filter"],
            "suggestions": ["add a CODE node"],
        }}
        result = get_agent_response(node, new_values, mock_ctx)
        assert "found issues" in result
        assert "missing trader_id" in result


class TestEvaluatorFormatter:
    def test_goal_satisfied(self, mock_ctx):
        node = {"type": "LLM_EVALUATOR", "config": {}}
        new_values = {"evaluator_status": {"done": True, "confidence": 0.9}}
        result = get_agent_response(node, new_values, mock_ctx)
        assert "satisfied" in result

    def test_goal_not_satisfied(self, mock_ctx):
        node = {"type": "LLM_EVALUATOR", "config": {}}
        new_values = {"evaluator_status": {
            "done": False,
            "missing": ["trader_id enrichment"],
        }}
        result = get_agent_response(node, new_values, mock_ctx)
        assert "not satisfied" in result
        assert "trader_id" in result


class TestLoopControllerFormatter:
    def test_continue(self, mock_ctx):
        node = {"type": "LOOP_CONTROLLER", "config": {}}
        new_values = {"loop_decision": {"continue": True, "iteration": 2}}
        result = get_agent_response(node, new_values, mock_ctx)
        assert "continue" in result
        assert "2" in result

    def test_stop(self, mock_ctx):
        node = {"type": "LOOP_CONTROLLER", "config": {}}
        new_values = {"loop_decision": {
            "continue": False,
            "stop_reason": "max iterations",
            "iteration": 5,
        }}
        result = get_agent_response(node, new_values, mock_ctx)
        assert "stop" in result
        assert "max iterations" in result


class TestSynthesizerFormatter:
    def test_with_text_response(self, mock_ctx):
        node = {"type": "LLM_SYNTHESIZER", "config": {}}
        new_values = {"final_output": {"response": "Analysis complete."}}
        result = get_agent_response(node, new_values, mock_ctx)
        assert result == "Analysis complete."

    def test_with_string_output(self, mock_ctx):
        node = {"type": "LLM_SYNTHESIZER", "config": {}}
        new_values = {"final_output": "Direct string output"}
        result = get_agent_response(node, new_values, mock_ctx)
        assert result == "Direct string output"


class TestOutputNameOverride:
    def test_custom_output_name(self, mock_ctx):
        node = {"type": "LLM_SYNTHESIZER", "config": {"output_name": "my_output"}}
        new_values = {"my_output": "Custom output value"}
        result = get_agent_response(node, new_values, mock_ctx)
        assert result == "Custom output value"


class TestGuardrailFormatter:
    def test_passed(self, mock_ctx):
        node = {"type": "GUARDRAIL", "config": {}}
        new_values = {"guardrail_result": {"valid": True}}
        result = get_agent_response(node, new_values, mock_ctx)
        assert "passed" in result

    def test_failed_with_errors(self, mock_ctx):
        node = {"type": "GUARDRAIL", "config": {}}
        new_values = {"guardrail_result": {
            "valid": False,
            "errors": ["PII detected in output"],
        }}
        result = get_agent_response(node, new_values, mock_ctx)
        assert "failed" in result
        assert "PII" in result
