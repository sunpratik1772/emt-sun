from __future__ import annotations

import json

from generation.harness.runner import AgentRunner
from generation.planner import Planner


class _StaticLLM:
    def __init__(self, workflow: dict) -> None:
        self.raw = json.dumps(workflow)

    def complete(self, system_prompt: str, history: list[dict], user_turn: str) -> str:
        return self.raw


def test_plan_profile_denies_edit_tool(monkeypatch) -> None:
    monkeypatch.setenv("HARNESS_AGENT_PROFILE", "plan")
    runner = AgentRunner(
        planner=Planner(
            _StaticLLM(
                {
                    "schema_version": "1.0",
                    "nodes": [{"id": "n01", "type": "manual_trigger", "label": "Start", "config": {}}],
                    "edges": [],
                }
            )
        )
    )
    events = [ev.to_json() for ev in runner.stream("fix this", current_workflow={"nodes": [], "edges": []})]
    assert events[-1]["phase"] == "complete"
    assert events[-1]["status"] == "error"
    assert events[-1]["workflow"] is None
    assert events[-1]["error_code"] == "PERMISSION_DENIED"
