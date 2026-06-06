from __future__ import annotations

from generation.harness.state import AgentEvent, AgentPhase
from copilot.agent_sse_adapter import AgentSseAdapter


def test_adapter_preserves_custom_stage_labels() -> None:
    adapter = AgentSseAdapter()
    frames = adapter.convert(AgentEvent(AgentPhase.PLANNING, "Some Custom Stage Label", detail="x"))
    stage = next(f for f in frames if f.get("type") == "agent_stage")
    assert stage["stage"] == "Some Custom Stage Label"


def test_adapter_maps_technical_labels() -> None:
    adapter = AgentSseAdapter()
    frames = adapter.convert(AgentEvent(AgentPhase.PLANNING, "dispatch_parallel_tasks", detail="x"))
    stage = next(f for f in frames if f.get("type") == "agent_stage")
    assert stage["stage"] == "Planning workflow"


def test_adapter_maps_subagents_by_type_default() -> None:
    adapter = AgentSseAdapter()
    # Test explore subagent default fallback
    frames1 = adapter.convert(
        AgentEvent(
            AgentPhase.PLANNING,
            "parallel_subagent",
            detail="Data access plan",
            data={"task_id": "t1", "subagent_name": "Data access plan", "subagent_type": "explore"},
        )
    )
    stage1 = next(f for f in frames1 if f.get("type") == "agent_stage")
    assert stage1["stage"] == "Checking data sources"
    assert stage1["subagent_name"] == "Data access plan"

    # Test general subagent default fallback
    frames2 = adapter.convert(
        AgentEvent(
            AgentPhase.PLANNING,
            "parallel_subagent",
            detail="Topology plan",
            data={"task_id": "t2", "subagent_name": "Topology plan", "subagent_type": "general"},
        )
    )
    stage2 = next(f for f in frames2 if f.get("type") == "agent_stage")
    assert stage2["stage"] == "Designing workflow steps"
    assert stage2["subagent_name"] == "Topology plan"


def test_adapter_maps_subagents_by_type_custom_prompt() -> None:
    # Pass user_request with postgres and hono todo-api
    adapter = AgentSseAdapter(user_request="Create to-do list function with postgres and hono")
    
    # Test explore subagent with Postgres
    frames1 = adapter.convert(
        AgentEvent(
            AgentPhase.PLANNING,
            "parallel_subagent",
            detail="Data access plan",
            data={"task_id": "t1", "subagent_name": "Data access plan", "subagent_type": "explore"},
        )
    )
    stage1 = next(f for f in frames1 if f.get("type") == "agent_stage")
    assert stage1["stage"] == "Checking data sources"
    assert stage1["subagent_name"] == "Data access plan"

    # Test general subagent with Hono API
    frames2 = adapter.convert(
        AgentEvent(
            AgentPhase.PLANNING,
            "parallel_subagent",
            detail="Topology plan",
            data={"task_id": "t2", "subagent_name": "Topology plan", "subagent_type": "general"},
        )
    )
    stage2 = next(f for f in frames2 if f.get("type") == "agent_stage")
    assert stage2["stage"] == "Designing workflow steps"
    assert stage2["subagent_name"] == "Topology plan"


def test_adapter_distinguishes_parallel_general_tasks() -> None:
    adapter = AgentSseAdapter()
    frames_topo = adapter.convert(
        AgentEvent(
            AgentPhase.PLANNING,
            "parallel_subagent",
            detail="Topology and action plan",
            data={
                "task_id": "t-topo",
                "subagent_name": "Topology and action plan",
                "subagent_type": "general",
            },
        )
    )
    frames_out = adapter.convert(
        AgentEvent(
            AgentPhase.PLANNING,
            "parallel_subagent",
            detail="Output artifact plan",
            data={
                "task_id": "t-out",
                "subagent_name": "Output artifact plan",
                "subagent_type": "general",
            },
        )
    )
    topo = next(f for f in frames_topo if f.get("type") == "agent_stage")
    out = next(f for f in frames_out if f.get("type") == "agent_stage")
    assert topo["stage"] == "Designing workflow steps"
    assert out["stage"] == "Planning export"
    assert topo["subagent_name"] == "Topology and action plan"
    assert out["subagent_name"] == "Output artifact plan"
    assert topo["subagent_name"] != out["subagent_name"]


def test_adapter_concurrent_stage_ids() -> None:
    adapter = AgentSseAdapter()
    # Start t1
    frames1 = adapter.convert(
        AgentEvent(
            AgentPhase.PLANNING,
            "parallel_subagent",
            detail="explore task",
            data={"task_id": "t1", "subagent_type": "explore"},
        )
    )
    id1 = next(f for f in frames1 if f.get("type") == "agent_stage")["stage_id"]

    # Start t2
    frames2 = adapter.convert(
        AgentEvent(
            AgentPhase.PLANNING,
            "parallel_subagent",
            detail="general task",
            data={"task_id": "t2", "subagent_type": "general"},
        )
    )
    id2 = next(f for f in frames2 if f.get("type") == "agent_stage")["stage_id"]

    # They should have different stage IDs
    assert id1 != id2

    # Done t1 should pop the correct stage ID
    frames1_done = adapter.convert(
        AgentEvent(
            AgentPhase.PLANNING,
            "parallel_subagent",
            status="done",
            detail="explore task finished",
            data={"task_id": "t1", "subagent_type": "explore"},
        )
    )
    done_id1 = next(f for f in frames1_done if f.get("type") == "agent_stage")["stage_id"]
    assert done_id1 == id1


def test_adapter_done_parallel_includes_outcome_text() -> None:
    adapter = AgentSseAdapter()
    frames = adapter.convert(
        AgentEvent(
            AgentPhase.PLANNING,
            "parallel_subagent",
            status="done",
            detail="Branch and alert logic",
            data={
                "task_id": "t1",
                "subagent_name": "Branch and alert logic",
                "subagent_type": "general",
                "outcome": "Use condition branches when spread_pips exceeds threshold.",
            },
        )
    )
    stage = next(f for f in frames if f.get("type") == "agent_stage")
    assert stage["outcome"] == "Use condition branches when spread_pips exceeds threshold."
