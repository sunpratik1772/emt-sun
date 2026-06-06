from __future__ import annotations

import json

from generation.harness.runner import AgentRunner
from generation.planner import Planner


class _CountingLLM:
    def __init__(self, workflow: dict) -> None:
        self._raw = json.dumps(workflow)
        self.calls: list[str] = []

    def complete(self, system_prompt: str, history: list[dict], user_turn: str) -> str:
        self.calls.append(user_turn)
        return self._raw


class _AlwaysInvalidValidator:
    def validate(self, workflow: dict | None) -> dict:
        return {
            "valid": False,
            "errors": [{"code": "CYCLE", "message": "DAG contains a cycle", "severity": "error"}],
            "warnings": [],
            "summary": "1 error(s)",
        }


def test_runner_never_exceeds_configured_max_steps(monkeypatch) -> None:
    monkeypatch.setenv("HARNESS_MAX_STEPS", "1")
    llm = _CountingLLM(
        {
            "schema_version": "1.0",
            "nodes": [{"id": "n01", "type": "ALERT_TRIGGER", "label": "Alert"}],
            "edges": [],
        }
    )
    runner = AgentRunner(
        planner=Planner(llm),
        validator=_AlwaysInvalidValidator(),
    )
    runner.runtime_smoke_enabled = False

    state = runner.run("create a workflow", max_attempts=5)

    assert len(llm.calls) == 1
    assert state.step_count == 1
    assert state.step_budget_hit is True


def test_last_step_instruction_is_injected(monkeypatch) -> None:
    monkeypatch.setenv("HARNESS_MAX_STEPS", "1")
    llm = _CountingLLM(
        {
            "schema_version": "1.0",
            "nodes": [{"id": "n01", "type": "ALERT_TRIGGER", "label": "Alert"}],
            "edges": [],
        }
    )
    runner = AgentRunner(
        planner=Planner(llm),
        validator=_AlwaysInvalidValidator(),
    )
    runner.runtime_smoke_enabled = False

    runner.run("create a workflow", max_attempts=2)

    assert llm.calls
    assert "[FINAL STEP]" in llm.calls[0]
