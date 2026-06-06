"""Tests for studio_active / placeholder node visibility."""
from __future__ import annotations

from engine.node_availability import is_studio_active, is_studio_placeholder
from engine.registry import NODE_SPECS, placeholder_specs


def test_outlook_and_teams_are_placeholders_not_active() -> None:
    for tid in ("outlook", "teams"):
        spec = NODE_SPECS[tid]
        assert not is_studio_active(spec)
        assert is_studio_placeholder(spec)


def test_legacy_github_node_hidden_from_studio() -> None:
    spec = NODE_SPECS["github"]
    assert not is_studio_active(spec)
    assert not is_studio_placeholder(spec)


def test_jira_mcp_nodes_are_active() -> None:
    for tid in ("jira_mcp", "confluence_mcp", "github_mcp"):
        spec = NODE_SPECS[tid]
        assert is_studio_active(spec)
        assert not is_studio_placeholder(spec)


def test_legacy_mcp_hidden_from_studio() -> None:
    spec = NODE_SPECS["mcp"]
    assert not is_studio_active(spec)
    assert not is_studio_placeholder(spec)


def test_placeholder_specs_lists_outlook_teams() -> None:
    ids = {s.type_id for s in placeholder_specs()}
    assert ids == {"outlook", "teams"}
