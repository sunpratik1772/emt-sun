"""Progress narration for Sherpa generation timeline."""
from __future__ import annotations

from copilot.progress_narration import progress_description, stage_title
from generation.harness.state import AgentEvent, AgentPhase


def test_parallel_done_shows_planning_outcome() -> None:
    event = AgentEvent(
        AgentPhase.PLANNING,
        "parallel_subagent",
        status="done",
        detail="Data access plan",
        data={
            "subagent_name": "Data access plan",
            "subagent_type": "explore",
            "outcome": "Use db_query on market_ticks with spread_pips column.",
        },
    )
    assert stage_title(event) == "Checking data sources"
    assert "market_ticks" in progress_description(event)
    assert progress_description(event).endswith(".")


def test_smoke_running_description() -> None:
    event = AgentEvent(
        AgentPhase.FINALIZING,
        "Runtime smoke test",
        status="running",
        detail="Executing reduced-sample workflow for runtime validity",
    )
    assert "reduced-sample" in progress_description(event).lower()
