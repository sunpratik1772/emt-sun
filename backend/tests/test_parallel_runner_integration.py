from __future__ import annotations

import json
import time

from generation.harness.runner import AgentRunner
from generation.harness.task_manager import TaskManager
from generation.planner import Planner


class _StaticLLM:
    def __init__(self, workflow: dict) -> None:
        self.raw = json.dumps(workflow)

    def complete(self, system_prompt: str, history: list[dict], user_turn: str) -> str:
        return self.raw


def _executor(task):
    time.sleep(0.1)
    return (f"ok:{task.description}", {"id": task.task_id})


class _FakeParallelAdapter:
    def single_shot(self, prompt: str, **_: object) -> str:
        return f"llm-subtask:{prompt.splitlines()[0]}"


def test_runner_dispatches_and_collects_parallel_tasks(monkeypatch) -> None:
    monkeypatch.setenv("HARNESS_ENABLE_PARALLEL_TASKS", "1")
    task_manager = TaskManager(executor=_executor)
    runner = AgentRunner(
        planner=Planner(
            _StaticLLM(
                {
                    "schema_version": "1.0",
                    "nodes": [{"id": "n01", "type": "manual_trigger", "label": "Start", "config": {}}],
                    "edges": [],
                }
            )
        ),
        task_manager=task_manager,
    )
    runner.runtime_smoke_enabled = False

    events = [ev.to_json() for ev in runner.stream("merge orders.csv with products.csv and export csv", max_attempts=1)]
    planning = [e for e in events if e.get("phase") == "planning"]
    assert any(e.get("label") == "dispatch_parallel_tasks" for e in planning)
    collect = next(e for e in planning if e.get("label") == "collect_parallel_results")
    assert len(collect.get("parallel_results", [])) >= 2
    assert any(e.get("label") == "parallel_subagent" for e in planning)


def test_runner_uses_blueprint_parallel_plan(monkeypatch) -> None:
    monkeypatch.setenv("HARNESS_ENABLE_PARALLEL_TASKS", "1")
    task_manager = TaskManager(executor=_executor)
    runner = AgentRunner(
        planner=Planner(
            _StaticLLM(
                {
                    "schema_version": "1.0",
                    "nodes": [{"id": "n01", "type": "manual_trigger", "label": "Start", "config": {}}],
                    "edges": [],
                }
            )
        ),
        task_manager=task_manager,
    )
    runner.runtime_smoke_enabled = False

    scenario = "Use db_query to monitor market_ticks for spread_pips > 100 and post alert to confluence page"
    events = [ev.to_json() for ev in runner.stream(scenario, max_attempts=1)]
    retrieving = [e for e in events if e.get("phase") == "retrieving"]
    assert retrieving
    assert any(e.get("blueprint_id") == "market_ticks_spread_monitor" for e in retrieving)
    planning = [e for e in events if e.get("phase") == "planning"]
    collect = next(e for e in planning if e.get("label") == "collect_parallel_results")
    assert len(collect.get("parallel_results", [])) >= 3


def test_runner_parallel_tasks_can_use_llm_executor(monkeypatch) -> None:
    monkeypatch.setenv("HARNESS_ENABLE_PARALLEL_TASKS", "1")
    monkeypatch.setenv("HARNESS_PARALLEL_LLM_SUBAGENTS", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    runner = AgentRunner(
        planner=Planner(
            _StaticLLM(
                {
                    "schema_version": "1.0",
                    "nodes": [{"id": "n01", "type": "manual_trigger", "label": "Start", "config": {}}],
                    "edges": [],
                }
            )
        ),
        parallel_llm_adapter=_FakeParallelAdapter(),
    )
    runner.runtime_smoke_enabled = False

    scenario = "Use db_query to monitor market_ticks for spread_pips > 100 and post alert to confluence page"
    events = [ev.to_json() for ev in runner.stream(scenario, max_attempts=1)]
    planning = [e for e in events if e.get("phase") == "planning"]
    collect = next(e for e in planning if e.get("label") == "collect_parallel_results")
    results = collect.get("parallel_results", [])
    assert results
    assert any(str(r.get("result_text", "")).startswith("llm-subtask:Subtask:") for r in results)
