"""
Shared context classification and prompt enrichment for Copilot generation.

Both AgentRunner and WorkflowCopilot use this module so intent routing,
template/example injection, and memory blocks stay in one place.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from copilot.build_narration import contextual_understanding_detail
from .blueprint_router import BlueprintDecision, render_blueprint_hint, select_blueprint
from .intent import Intent, classify
from .retriever import ContextRetriever, RetrievedContext


@dataclass(frozen=True)
class GenerationContext:
    """Classified intent plus retrieved materials for one generation turn."""

    intent: Intent
    retrieved: RetrievedContext
    blueprint: BlueprintDecision | None
    enrichment_suffix: str


def build_generation_context(
    scenario: str,
    *,
    current_workflow: dict | None,
    known_datasets: set[str],
    known_node_types: set[str],
    retriever: ContextRetriever,
) -> GenerationContext:
    intent = classify(
        scenario,
        current_workflow=current_workflow,
        known_datasets=known_datasets,
        known_node_types=known_node_types,
    )
    blueprint = select_blueprint(scenario, intent)
    retrieved = retriever.retrieve(intent)
    return GenerationContext(
        intent=intent,
        retrieved=retrieved,
        blueprint=blueprint,
        enrichment_suffix=format_user_enrichment(retrieved, intent, blueprint=blueprint),
    )


def format_user_enrichment(
    retrieved: RetrievedContext,
    intent: Intent,
    *,
    blueprint: BlueprintDecision | None = None,
) -> str:
    """Append structured context blocks to the user turn sent to the planner."""
    enrichments: list[str] = []

    if retrieved.template_skeleton and intent.mode == "create":
        enrichments.append(
            "\n\n<template_skeleton>\n"
            "Use this vetted skeleton as a starting point. "
            "Adapt it to the user's request — add/remove/rewire nodes as needed.\n"
            + json.dumps(retrieved.template_skeleton, indent=2)[:6000]
            + "\n</template_skeleton>"
        )

    for ex in retrieved.example_workflows[:2]:
        enrichments.append(
            f"\n\n<example_workflow name=\"{ex['name']}\">\n"
            + json.dumps(ex["skeleton"], indent=2)[:4000]
            + "\n</example_workflow>"
        )

    if retrieved.memory_text:
        enrichments.append(
            "\n\n<copilot_memory>\n"
            + retrieved.memory_text[:1500]
            + "\n</copilot_memory>"
        )

    hint = render_blueprint_hint(blueprint)
    if hint:
        enrichments.append(hint)

    return "".join(enrichments)


def intent_summary_detail(
    intent: Intent,
    *,
    editing_mode: bool,
    current_workflow: dict | None,
    recent_errors: list[dict] | None,
    scenario: str,
) -> str:
    if editing_mode and current_workflow is not None:
        base = f"Edit of {len(current_workflow.get('nodes', []))}-node workflow"
        if recent_errors:
            base += f" · {len(recent_errors)} error(s) to fix"
        return base
    return contextual_understanding_detail(scenario, intent)


def retrieve_summary_parts(retrieved: RetrievedContext, skill_count: int) -> list[str]:
    parts = [f"{skill_count} skills"]
    if retrieved.template_name:
        parts.append(f"template: {retrieved.template_name}")
    if retrieved.example_workflows:
        parts.append(f"{len(retrieved.example_workflows)} example(s)")
    if retrieved.memory_text:
        parts.append("memory loaded")
    parts.append(f"matched: {', '.join(retrieved.matched_skills) or '(none)'}")
    return parts


def known_datasets() -> set[str]:
    try:
        from connectors import get_registry

        return {s.id for s in get_registry().all()}
    except Exception:
        return set()
