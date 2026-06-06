"""Tests for agent.harness.intent — keyword-driven intent classification."""
from __future__ import annotations

import pytest
from generation.harness.intent import Intent, classify, is_advisory_question_heuristic


class TestClassifyMode:
    def test_create_mode_when_no_workflow(self):
        intent = classify("build a front-running workflow")
        assert intent.mode == "create"

    def test_edit_mode_when_workflow_present(self):
        intent = classify("fix this node", current_workflow={"nodes": [], "edges": []})
        assert intent.mode == "edit"


class TestScenarioExtraction:
    def test_front_running_detected(self):
        intent = classify("detect front-running on FX desk")
        assert "front-running" in intent.scenarios

    def test_spoofing_detected(self):
        intent = classify("build spoofing alert for equities")
        assert "spoofing" in intent.scenarios

    def test_multiple_scenarios(self):
        intent = classify("detect spoofing and layering patterns")
        assert "spoofing" in intent.scenarios
        assert "layering" in intent.scenarios

    def test_no_scenario_for_generic(self):
        intent = classify("merge two CSV files together")
        assert len(intent.scenarios) == 0


class TestActionExtraction:
    def test_create_action(self):
        intent = classify("create a workflow for alerts")
        assert "create" in intent.actions

    def test_fix_action(self):
        intent = classify("fix the broken nodes")
        assert "fix" in intent.actions

    def test_merge_action(self):
        intent = classify("merge orders and trades data")
        assert "merge" in intent.actions

    def test_multiple_actions(self):
        intent = classify("add a filter and remove the last node")
        assert "add" in intent.actions
        assert "remove" in intent.actions
        assert "filter" in intent.actions


class TestArtifactExtraction:
    def test_csv_artifact(self):
        intent = classify("export results to csv")
        assert "csv" in intent.artifacts

    def test_excel_artifact(self):
        intent = classify("generate an Excel spreadsheet")
        assert "excel" in intent.artifacts

    def test_email_artifact(self):
        intent = classify("send the report via email")
        assert "email" in intent.artifacts

    def test_no_artifacts(self):
        intent = classify("create a workflow for front-running")
        assert "email" not in intent.artifacts


class TestDatasetMatching:
    def test_known_dataset_matched(self):
        intent = classify(
            "query the orders dataset",
            known_datasets={"orders", "trades", "executions"},
        )
        assert "orders" in intent.datasets

    def test_unknown_dataset_not_matched(self):
        intent = classify(
            "query the orders dataset",
            known_datasets={"trades", "executions"},
        )
        assert "orders" not in intent.datasets

    def test_no_known_datasets(self):
        intent = classify("query orders")
        assert len(intent.datasets) == 0


class TestNodeTypeMatching:
    def test_explicit_node_type(self):
        intent = classify(
            "add a CODE node after the trigger",
            known_node_types={"CODE", "LLM_BASIC", "MERGE"},
        )
        assert "CODE" in intent.node_types

    def test_no_node_types(self):
        intent = classify(
            "build a front-running workflow",
            known_node_types={"CODE", "LLM_BASIC"},
        )
        assert len(intent.node_types) == 0


class TestIntentToDict:
    def test_serialization_roundtrip(self):
        intent = classify(
            "create front-running workflow with csv output",
            known_datasets={"orders"},
        )
        d = intent.to_dict()
        assert d["mode"] == "create"
        assert isinstance(d["scenarios"], list)
        assert isinstance(d["actions"], list)
        assert isinstance(d["artifacts"], list)


class TestAdvisoryQuestion:
    def test_troubleshooting_question(self):
        assert is_advisory_question_heuristic("so tell me what are my options to get it to work")

    def test_recovery_with_errors(self):
        assert is_advisory_question_heuristic(
            "what now",
            recent_errors=[{"message": "OUTLOOK_TENANT_ID required"}],
        )

    def test_build_command_not_advisory(self):
        assert not is_advisory_question_heuristic("build a workflow that sends outlook email")

    def test_scenario_prompt_not_advisory(self):
        assert not is_advisory_question_heuristic(
            "Find comms_messages with relevance_score > 0.8 and send an outlook email"
        )

    def test_resource_inventory_question(self):
        assert is_advisory_question_heuristic(
            "Show me the available FinCrime skills I can use in a workflow."
        )

    def test_use_in_workflow_not_build_command(self):
        assert is_advisory_question_heuristic("What skills can I use in a workflow?")
