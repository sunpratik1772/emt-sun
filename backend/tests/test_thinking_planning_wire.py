"""Planning monologue wired into downstream prompts."""
from __future__ import annotations

from generation.prompt_builder import _render_planning_monologue


def test_initial_prompt_includes_planning_monologue() -> None:
    from generation.prompt_builder import PromptBuilder

    pb = PromptBuilder()
    plan = (
        "User wants to improve Join Comms with validation and Outlook.\n"
        "Drafting now."
    )
    prompt = pb.initial_prompt(
        'Improve "Join Comms" with validation and Outlook.',
        current_workflow={"name": "Join Comms", "nodes": [], "edges": []},
        planning_monologue=plan,
    )
    assert "Sherpa planning (binding" in prompt
    assert "validation and Outlook" in prompt
    assert _render_planning_monologue(plan) in prompt


def test_chat_turn_includes_planning_monologue() -> None:
    from copilot.workflow_generator import WorkflowCopilot

    turn = WorkflowCopilot._format_chat_turn(
        "Why did the join fail?",
        planning_monologue="I'll trace orphan rows from the join step.\nDrafting the answer now.",
    )
    assert "binding" in turn.lower()
    assert "orphan rows" in turn
