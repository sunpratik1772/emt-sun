"""
Harness prompt scenario coverage — studio demos, node palette, error→fix flows.

Fast tests exercise intent + blueprint routing without LLM.
Integration tests (marked ``integration``) call Gemini when configured.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from generation.harness.blueprint_router import select_blueprint
from generation.harness.enrichment import build_generation_context, known_datasets
from generation.harness.intent import classify
from generation.harness.memory import MemoryManager
from generation.harness.runner import AgentRunner
from generation.planner import Planner
from generation.harness.retriever import ContextRetriever
from generation.validator_adapter import ValidatorAdapter
from copilot.workflow_generator import WorkflowCopilot
from engine.studio_nodes import STUDIO_APPROVED_NODE_TYPES

# ---------------------------------------------------------------------------
# Scenario catalog — one prompt per studio demo theme + difficult variants
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScenarioPrompt:
    name: str
    prompt: str
    expect_datasets: frozenset[str] = frozenset()
    expect_artifacts: frozenset[str] = frozenset()
    expect_blueprint: str | None = None
    expect_blueprint_not: frozenset[str] = frozenset()
    is_ambiguous_followup: bool = False
    node_types_hint: frozenset[str] = frozenset()
    live_generate: bool = True
    live_iterations: int = 4


STUDIO_SCENARIO_PROMPTS: tuple[ScenarioPrompt, ...] = (
    ScenarioPrompt(
        "01_mcp_ticket_swarm",
        "Chain MCP tools to triage support tickets and export results to Excel",
        expect_artifacts=frozenset({"excel"}),
        node_types_hint=frozenset({"jira_mcp", "confluence_mcp", "excel_output"}),
    ),
    ScenarioPrompt(
        "02_revenue_ai_pipeline",
        "Load orders.csv, group revenue by region, run an AI agent summary, "
        "score with evaluator, export multi-tab Excel",
        expect_datasets=frozenset({"orders.csv"}),
        expect_artifacts=frozenset({"excel"}),
        node_types_hint=frozenset({"csv_extract", "group_by", "agent", "evaluator", "excel_output"}),
    ),
    ScenarioPrompt(
        "03_hot_cold_leads_branch",
        "Load leads.csv, branch on score >= 80 with condition node, "
        "run per-row agent on hot leads, export two CSV files",
        expect_datasets=frozenset({"leads.csv"}),
        expect_artifacts=frozenset({"csv"}),
        node_types_hint=frozenset({"condition", "agent", "csv_output"}),
    ),
    ScenarioPrompt(
        "04_product_360_join",
        "Join orders.csv to products.csv on sku, compute line totals, export Excel workbook",
        expect_datasets=frozenset({"orders.csv", "products.csv"}),
        expect_artifacts=frozenset({"excel"}),
        expect_blueprint="excel_orders.csv_products.csv",
        node_types_hint=frozenset({"join", "map_transform", "excel_output"}),
    ),
    ScenarioPrompt(
        "05_web_github_mcp_briefing",
        "Fetch GitHub repo stats via http, merge with MCP Confluence pages, summarize with agent, CSV export",
        expect_artifacts=frozenset({"csv"}),
        node_types_hint=frozenset({"http", "data_merge", "agent", "confluence_mcp", "csv_output"}),
    ),
    ScenarioPrompt(
        "06_transform_obstacle_course",
        "csv_extract leads.csv then filter, map_transform, sort, deduplicate, select_columns, csv_output",
        expect_datasets=frozenset({"leads.csv"}),
        node_types_hint=frozenset({"filter", "map_transform", "sort", "deduplicate", "select_columns"}),
    ),
    ScenarioPrompt(
        "07_join_analyze_confluence",
        "Join hs_trades with hs_alerts on alert_id, calculate metrics, AI analyze, publish Confluence via MCP",
        expect_datasets=frozenset({"hs_trades", "hs_alerts"}),
        node_types_hint=frozenset({"join", "agent", "confluence_mcp"}),
    ),
    ScenarioPrompt(
        "08_starlark_margin",
        "Use code node with Starlark to compute margin from orders.csv and products.csv join",
        expect_datasets=frozenset({"orders.csv", "products.csv"}),
        node_types_hint=frozenset({"code", "join"}),
    ),
    ScenarioPrompt(
        "09_trades_risk_mcp",
        "Screen hs_trades for risk, publish Confluence digest and Jira issues via MCP",
        expect_datasets=frozenset({"hs_trades"}),
        node_types_hint=frozenset({"db_query", "confluence_mcp", "jira_mcp"}),
    ),
    ScenarioPrompt(
        "10_leads_tier_mcp",
        "Tier leads.csv with condition branches, publish top tier to Confluence and Jira via MCP",
        expect_datasets=frozenset({"leads.csv"}),
        node_types_hint=frozenset({"condition", "confluence_mcp", "jira_mcp"}),
    ),
    ScenarioPrompt(
        "11_trades_risk_digest",
        "Summarize hs_trades risk by trader and export a ranked CSV digest",
        expect_datasets=frozenset({"hs_trades"}),
        node_types_hint=frozenset({"group_by", "sort", "csv_output"}),
    ),
    ScenarioPrompt(
        "12_market_ticks_spread_monitor",
        "Use db_query on market_ticks, condition when spread_pips > 100, publish Confluence alert via MCP",
        expect_datasets=frozenset({"market_ticks"}),
        expect_blueprint="market_ticks_spread_monitor",
        node_types_hint=frozenset({"db_query", "condition", "confluence_mcp"}),
    ),
    ScenarioPrompt(
        "13_confluence_actions_jira",
        "Search Confluence for action items and create Jira backlog issues",
        expect_blueprint="confluence_actions_to_jira",
        node_types_hint=frozenset({"confluence_mcp", "jira_mcp"}),
    ),
    ScenarioPrompt(
        "14_alerts_ticks_join_publish",
        "Join hs_alerts with market_ticks on alert_id, filter high spread, "
        "publish Confluence digest and Jira follow-ups, export Excel pack",
        expect_datasets=frozenset({"hs_alerts", "market_ticks"}),
        expect_artifacts=frozenset({"excel"}),
        expect_blueprint="alerts_ticks_join_publish",
        node_types_hint=frozenset({"join", "confluence_mcp", "jira_mcp", "excel_output"}),
        live_iterations=6,
    ),
    ScenarioPrompt(
        "15_starlark_excel_colors",
        "Join hs_trades with hs_alerts, use Starlark code node for row coloring, "
        "export multi-tab Excel workbook",
        expect_datasets=frozenset({"hs_trades", "hs_alerts"}),
        expect_artifacts=frozenset({"excel"}),
        node_types_hint=frozenset({"join", "code", "excel_output"}),
    ),
    ScenarioPrompt(
        "excel_alerts_ticks_only",
        "Extract hs_alerts and market_ticks, join on alert_id, output to Excel AlertsMarketData.xlsx",
        expect_datasets=frozenset({"hs_alerts", "market_ticks"}),
        expect_artifacts=frozenset({"excel"}),
        expect_blueprint="excel_hs_alerts_market_ticks",
    ),
    ScenarioPrompt(
        "explicit_followup_spread_filter",
        "On the hs_alerts and market_ticks join, keep only rows where spread_pips >= 80 "
        "and sort by spread descending",
        expect_datasets=frozenset({"hs_alerts", "market_ticks"}),
        expect_blueprint_not=frozenset({"market_ticks_spread_monitor"}),
        node_types_hint=frozenset({"filter", "sort"}),
        live_generate=False,
    ),
    ScenarioPrompt(
        "ambiguous_followup_spread_filter",
        "Also make sure the join keeps only rows where spread_pips >= 80 "
        "and sort by spread descending",
        expect_datasets=frozenset(),
        expect_blueprint_not=frozenset({"market_ticks_spread_monitor"}),
        is_ambiguous_followup=True,
        node_types_hint=frozenset({"filter", "sort"}),
        live_generate=False,
    ),
)


def _broken_branch_workflow() -> dict[str, Any]:
    """Condition with two outputs but missing sourceHandle — triggers auto-fix."""
    return {
        "name": "Broken Branch Export",
        "description": "Deliberately invalid condition branches",
        "nodes": [
            {"id": "n01", "type": "manual_trigger", "label": "Start", "config": {}},
            {
                "id": "n02",
                "type": "csv_extract",
                "label": "Load leads",
                "config": {"source": "leads.csv"},
            },
            {
                "id": "n03",
                "type": "condition",
                "label": "Hot vs cold",
                "config": {"expression": "row.score >= 80"},
                "position": {"y": 200},
            },
            {
                "id": "n04",
                "type": "csv_output",
                "label": "Hot leads",
                "config": {"filename": "hot.csv"},
                "position": {"y": 80},
            },
            {
                "id": "n05",
                "type": "csv_output",
                "label": "Cold leads",
                "config": {"filename": "cold.csv"},
                "position": {"y": 320},
            },
        ],
        "edges": [
            {"from": "n01", "to": "n02"},
            {"from": "n02", "to": "n03"},
            {"from": "n03", "to": "n04"},
            {"from": "n03", "to": "n05"},
        ],
    }


def _fixed_branch_workflow() -> dict[str, Any]:
    wf = _broken_branch_workflow()
    wf["name"] = "Fixed Branch Export"
    for edge in wf["edges"]:
        if edge["from"] == "n03":
            edge["sourceHandle"] = "true" if edge["to"] == "n04" else "false"
    return wf


def _agent_row_dot_workflow() -> dict[str, Any]:
    return {
        "name": "Poem Agent (broken templates)",
        "nodes": [
            {"id": "n01", "type": "manual_trigger", "label": "Start", "config": {}},
            {
                "id": "n02",
                "type": "csv_extract",
                "label": "Leads",
                "config": {"source": "leads.csv"},
            },
            {
                "id": "n03",
                "type": "agent",
                "label": "Poem writer",
                "config": {
                    "mode": "perRow",
                    "prompt": "Write a haiku",
                    "task": "Company: {{row.company}}",
                    "rowTemplate": "Lead {{row.lead_id}} at {{row.company}}",
                },
            },
            {
                "id": "n04",
                "type": "csv_output",
                "label": "Output",
                "config": {"filename": "poems.csv"},
            },
        ],
        "edges": [
            {"from": "n01", "to": "n02"},
            {"from": "n02", "to": "n03"},
            {"from": "n03", "to": "n04"},
        ],
    }


class SequentialMockLLM:
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


@pytest.fixture
def scenario_memory(tmp_path):
    return MemoryManager(memory_dir=tmp_path / "memory")


@pytest.fixture
def scenario_copilot(scenario_memory):
    """Copilot with mock LLM for deterministic multi-turn tests."""
    mock = SequentialMockLLM([
        {
            "intent": "create_workflow",
            "answer": "Created alerts+ticks excel join.",
            "workflow": {
                "name": "Alerts Ticks Excel",
                "nodes": [
                    {"id": "s", "type": "manual_trigger", "label": "Start", "config": {}},
                    {
                        "id": "a",
                        "type": "db_query",
                        "label": "Alerts",
                        "config": {"query": "SELECT alert_id, trader_name FROM hs_alerts"},
                    },
                    {
                        "id": "t",
                        "type": "db_query",
                        "label": "Ticks",
                        "config": {"query": "SELECT alert_id, spread_pips FROM market_ticks"},
                    },
                    {
                        "id": "j",
                        "type": "join",
                        "label": "Join",
                        "config": {"leftKey": "alert_id", "rightKey": "alert_id", "joinType": "inner"},
                    },
                    {
                        "id": "x",
                        "type": "excel_output",
                        "label": "Export",
                        "config": {"filename": "AlertsMarketData.xlsx", "tabNames": "joined"},
                    },
                ],
                "edges": [
                    {"from": "s", "to": "a"},
                    {"from": "s", "to": "t"},
                    {"from": "a", "to": "j"},
                    {"from": "t", "to": "j"},
                    {"from": "j", "to": "x"},
                ],
            },
        },
        {
            "intent": "edit_workflow",
            "answer": "Added filter and sort.",
            "workflow": {
                "name": "Alerts Ticks Excel",
                "nodes": [
                    {"id": "s", "type": "manual_trigger", "label": "Start", "config": {}},
                    {
                        "id": "a",
                        "type": "db_query",
                        "label": "Alerts",
                        "config": {"query": "SELECT alert_id, trader_name FROM hs_alerts"},
                    },
                    {
                        "id": "t",
                        "type": "db_query",
                        "label": "Ticks",
                        "config": {"query": "SELECT alert_id, spread_pips FROM market_ticks"},
                    },
                    {
                        "id": "j",
                        "type": "join",
                        "label": "Join",
                        "config": {"leftKey": "alert_id", "rightKey": "alert_id", "joinType": "inner"},
                    },
                    {
                        "id": "f",
                        "type": "filter",
                        "label": "High spread",
                        "config": {"expression": "row.spread_pips >= 80"},
                    },
                    {
                        "id": "r",
                        "type": "sort",
                        "label": "Sort spread",
                        "config": {"sortBy": "spread_pips", "order": "desc"},
                    },
                    {
                        "id": "x",
                        "type": "excel_output",
                        "label": "Export",
                        "config": {"filename": "AlertsMarketData.xlsx", "tabNames": "joined"},
                    },
                ],
                "edges": [
                    {"from": "s", "to": "a"},
                    {"from": "s", "to": "t"},
                    {"from": "a", "to": "j"},
                    {"from": "t", "to": "j"},
                    {"from": "j", "to": "f"},
                    {"from": "f", "to": "r"},
                    {"from": "r", "to": "x"},
                ],
            },
        },
        {
            "intent": "create_workflow",
            "answer": "Still broken branch.",
            "workflow": _broken_branch_workflow(),
        },
        {
            "intent": "edit_workflow",
            "answer": "Fixed branch handles.",
            "workflow": _fixed_branch_workflow(),
        },
        {
            "intent": "create_workflow",
            "answer": "Agent with row templates.",
            "workflow": _agent_row_dot_workflow(),
        },
    ])
    cp = WorkflowCopilot()
    cp._memory = scenario_memory
    cp._retriever = ContextRetriever(memory=cp._memory)
    cp._runner = AgentRunner(
        planner=Planner(mock),
        prompt_builder=cp._prompt_builder,
        memory=cp._memory,
        retriever=cp._retriever,
    )
    cp._runner.runtime_smoke_enabled = False
    return cp, mock


class TestScenarioPromptRouting:
    """Every studio-aligned prompt classifies intent and routes blueprints."""

    @pytest.mark.parametrize("scenario", STUDIO_SCENARIO_PROMPTS, ids=lambda s: s.name)
    def test_intent_and_blueprint(self, scenario: ScenarioPrompt) -> None:
        ds = known_datasets()
        intent = classify(scenario.prompt, known_datasets=ds)
        for artifact in scenario.expect_artifacts:
            assert artifact in intent.artifacts, (
                f"{scenario.name}: expected artifact {artifact}, got {intent.artifacts}"
            )
        for dataset in scenario.expect_datasets:
            assert dataset in intent.datasets, (
                f"{scenario.name}: expected dataset {dataset}, got {intent.datasets}"
            )
        decision = select_blueprint(scenario.prompt, intent)
        if scenario.expect_blueprint:
            assert decision is not None, f"{scenario.name}: expected blueprint"
            assert decision.blueprint_id == scenario.expect_blueprint
        for forbidden in scenario.expect_blueprint_not:
            if decision is not None:
                assert decision.blueprint_id != forbidden, (
                    f"{scenario.name}: must not route to {forbidden}"
                )
        if decision is not None:
            compact = decision.compact_workflow()
            assert compact.get("nodes")


class TestFiveTurnHarnessSession:
    """Multi-turn: create → edit → broken create → fix → agent auto-fix."""

    def test_five_prompt_conversation(self, scenario_copilot) -> None:
        cp, mock = scenario_copilot

        r1 = cp.generate_with_critic(
            "Join hs_alerts and market_ticks on alert_id, export AlertsMarketData.xlsx",
            iterations=1,
        )
        assert r1["success"]
        wf1 = r1["workflow"]
        assert any(n["type"] == "excel_output" for n in wf1["nodes"])

        r2 = cp.generate_with_critic(
            "Add filter spread_pips >= 80 and sort by spread descending before Excel export",
            iterations=1,
            current_workflow=wf1,
        )
        assert r2["success"]
        types = {n["type"] for n in r2["workflow"]["nodes"]}
        assert "filter" in types
        assert "sort" in types

        r3 = cp.generate_with_critic(
            "Create leads.csv hot/cold branch workflow with two csv outputs",
            iterations=3,
        )
        assert r3["success"], r3.get("errors")
        assert r3.get("auto_fixes_applied") or any(
            e.get("sourceHandle") for e in r3["workflow"]["edges"] if e.get("from") == "n03"
        )

        r4 = cp.generate_with_critic(
            "Fix the condition branch wiring — hot leads on true, cold on false",
            iterations=3,
            current_workflow=r3["workflow"],
            recent_errors=r3.get("errors") or [],
        )
        assert r4["success"]

        r5 = cp.generate_with_critic(
            "Build per-row agent on leads.csv that writes poems using company name",
            iterations=1,
        )
        assert r5["success"]
        agent = next(n for n in r5["workflow"]["nodes"] if n["type"] == "agent")
        cfg = agent["config"]
        combined = " ".join(str(cfg.get(k, "")) for k in ("task", "rowTemplate", "prompt"))
        assert "{{row." not in combined

        assert len(mock.calls) >= 5


class TestErrorThenFixAutoFix:
    def test_preflight_fixes_broken_branch_without_llm(self) -> None:
        wf = _broken_branch_workflow()
        first = ValidatorAdapter().validate(wf)
        assert first["valid"] is False

        from copilot.preflight import preflight_dag

        repaired, validation = preflight_dag(wf)
        assert validation.valid
        handles = {
            e["to"]: e.get("sourceHandle")
            for e in repaired["edges"]
            if e.get("from") == "n03"
        }
        assert handles.get("n04") == "true"
        assert handles.get("n05") == "false"

    def test_agent_row_dot_auto_normalized(self) -> None:
        from generation.repair.auto_fixer import AutoFixer

        wf = _agent_row_dot_workflow()
        AutoFixer().fix(wf, [])
        agent = next(n for n in wf["nodes"] if n["type"] == "agent")
        assert "{{row." not in agent["config"]["task"]
        assert "{{company}}" in agent["config"]["task"]


def _gemini_configured() -> bool:
    try:
        from llm import gemini_configured, gemini_api_key

        key = gemini_api_key()
        if not key or key == "mock_key_for_testing":
            return False
        return bool(gemini_configured())
    except Exception:
        key = os.environ.get("GEMINI_API_KEY", "")
        return bool(key) and key != "mock_key_for_testing"


@pytest.mark.integration
@pytest.mark.skipif(not _gemini_configured(), reason="GEMINI_API_KEY not configured")
class TestLiveHarnessPrompts:
    """Every scenario prompt exercised against live Gemini."""

    @pytest.fixture
    def live_copilot(self, tmp_path):
        cp = WorkflowCopilot()
        cp._memory = MemoryManager(memory_dir=tmp_path / "live_memory")
        cp._retriever = ContextRetriever(memory=cp._memory)
        cp._runner = AgentRunner(
            planner=Planner(),
            prompt_builder=cp._prompt_builder,
            memory=cp._memory,
            retriever=cp._retriever,
        )
        cp._runner.runtime_smoke_enabled = False
        cp._runner.parallel_enabled = False
        return cp

    @staticmethod
    def _assert_valid_workflow(result: dict, *, scenario_name: str) -> dict:
        if not result.get("success"):
            validation = result.get("validation") or {}
            errors = validation.get("errors") if isinstance(validation, dict) else result.get("errors")
            pytest.fail(
                f"{scenario_name}: generation failed — {result.get('error')} errors={errors}"
            )
        wf = result["workflow"]
        assert wf and len(wf.get("nodes") or []) >= 3
        types = {n.get("type") for n in wf["nodes"]}
        unknown = types - STUDIO_APPROVED_NODE_TYPES
        assert not unknown, f"{scenario_name}: unknown types {unknown}"
        return wf

    def _generate(self, cp, prompt: str, *, iterations: int = 4, **kwargs) -> dict:
        result: dict = {"success": False, "error": "not started"}
        for trial in range(4):
            result = cp.generate_with_critic(prompt, iterations=iterations, **kwargs)
            if result.get("success"):
                time.sleep(1)
                return result
            err = (result.get("error") or "").lower()
            if trial < 3:
                time.sleep(3 * (trial + 1))
                continue
        return result

    def test_live_all_studio_scenarios_serial(self, live_copilot) -> None:
        """Run every studio prompt against Gemini in one session (avoids rate-limit flakes)."""
        failures: list[str] = []
        passed: list[str] = []
        for scenario in STUDIO_SCENARIO_PROMPTS:
            if not scenario.live_generate:
                continue
            result = self._generate(
                live_copilot,
                scenario.prompt,
                iterations=scenario.live_iterations,
            )
            if not result.get("success"):
                failures.append(f"{scenario.name}: {result.get('error')}")
                continue
            try:
                wf = self._assert_valid_workflow(result, scenario_name=scenario.name)
                if scenario.node_types_hint:
                    types = {n.get("type") for n in wf["nodes"]}
                    if not scenario.node_types_hint & types:
                        failures.append(
                            f"{scenario.name}: missing hint types {scenario.node_types_hint - types}"
                        )
                        continue
                passed.append(scenario.name)
            except Exception as exc:
                failures.append(str(exc))
        assert not failures, (
            f"Live scenario failures ({len(failures)}/{len(passed) + len(failures)}):\n"
            + "\n".join(failures)
        )

    def test_live_ambiguous_followup_after_join(self, live_copilot) -> None:
        """Context-free follow-up must not pick spread monitor; harness should edit join in place."""
        cp = live_copilot
        r1 = self._generate(
            cp,
            "Join hs_alerts and market_ticks on alert_id, export to Excel AlertsMarketData.xlsx",
        )
        wf1 = self._assert_valid_workflow(r1, scenario_name="join_create")

        ambiguous = (
            "Also make sure the join keeps only rows where spread_pips >= 80 "
            "and sort by spread descending"
        )
        intent = classify(ambiguous, current_workflow=wf1, known_datasets=known_datasets())
        decision = select_blueprint(ambiguous, intent)
        assert decision is None or decision.blueprint_id != "market_ticks_spread_monitor"

        r2 = self._generate(cp, ambiguous, current_workflow=wf1)
        wf2 = self._assert_valid_workflow(r2, scenario_name="ambiguous_followup")
        types = {n.get("type") for n in wf2["nodes"]}
        assert "filter" in types
        assert "sort" in types

    def test_live_explicit_followup_after_join(self, live_copilot) -> None:
        cp = live_copilot
        r1 = self._generate(
            cp,
            "Extract hs_alerts and market_ticks, join on alert_id, output to Excel AlertsMarketData.xlsx",
        )
        wf1 = self._assert_valid_workflow(r1, scenario_name="excel_join")

        explicit = (
            "On the hs_alerts and market_ticks join, keep only rows where spread_pips >= 80 "
            "and sort by spread descending"
        )
        intent = classify(explicit, current_workflow=wf1, known_datasets=known_datasets())
        decision = select_blueprint(explicit, intent)
        assert decision is None or decision.blueprint_id != "market_ticks_spread_monitor"

        r2 = self._generate(cp, explicit, current_workflow=wf1)
        wf2 = self._assert_valid_workflow(r2, scenario_name="explicit_followup")
        assert "filter" in {n.get("type") for n in wf2["nodes"]}

    def test_live_five_turn_session(self, live_copilot) -> None:
        cp = live_copilot

        r1 = self._generate(
            cp,
            "Join hs_alerts and market_ticks on alert_id, export AlertsMarketData.xlsx",
        )
        wf1 = self._assert_valid_workflow(r1, scenario_name="turn1")

        r2 = self._generate(
            cp,
            "Add filter spread_pips >= 80 and sort by spread_pips descending before Excel export",
            current_workflow=wf1,
        )
        self._assert_valid_workflow(r2, scenario_name="turn2")

        r3 = self._generate(
            cp,
            "Create leads.csv hot/cold branch workflow with two csv outputs",
        )
        self._assert_valid_workflow(r3, scenario_name="turn3")

        r4 = self._generate(
            cp,
            "Build per-row agent on leads.csv that writes a short poem using the company field",
        )
        wf4 = self._assert_valid_workflow(r4, scenario_name="turn4")
        agent = next(n for n in wf4["nodes"] if n.get("type") == "agent")
        combined = " ".join(
            str(agent.get("config", {}).get(k, "")) for k in ("task", "rowTemplate", "prompt")
        )
        assert "{{row." not in combined

        broken = _broken_branch_workflow()
        validation = ValidatorAdapter().validate(broken)
        assert validation["valid"] is False

        r5 = self._generate(
            cp,
            "Fix validation errors on the condition branch — wire true/false handles correctly",
            iterations=5,
            current_workflow=broken,
            recent_errors=validation["errors"],
        )
        self._assert_valid_workflow(r5, scenario_name="turn5_error_fix")
