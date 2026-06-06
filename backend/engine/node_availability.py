"""Studio node visibility — active palette nodes vs UI-only placeholders vs legacy."""
from __future__ import annotations

from .node_spec import NodeSpec

LEGACY_CONFIG_TAGS: frozenset[str] = frozenset({"legacy", "deprecated"})


def is_studio_active(spec: NodeSpec) -> bool:
    """Fully accessible in palette, agent, prompts, and prompt builder."""
    if spec.ui.get("studio_active") is False:
        return False
    tags = {str(t).strip().lower() for t in (spec.ui.get("config_tags") or [])}
    return LEGACY_CONFIG_TAGS.isdisjoint(tags)


def is_studio_placeholder(spec: NodeSpec) -> bool:
    """Shown in the palette as coming-soon only — hidden from agent and prompts."""
    if is_studio_active(spec):
        return False
    if spec.ui.get("studio_active") is not False:
        return False
    tags = {str(t).strip().lower() for t in (spec.ui.get("config_tags") or [])}
    return LEGACY_CONFIG_TAGS.isdisjoint(tags)


def agent_visible_type_ids() -> frozenset[str]:
    """Node types exposed to agent, prompts, and prompt builder."""
    from .registry import all_specs

    return frozenset(s.type_id for s in all_specs())


def is_agent_visible_type(type_id: str) -> bool:
    return str(type_id or "").strip() in agent_visible_type_ids()
