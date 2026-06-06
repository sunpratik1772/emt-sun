"""Ensure MCP + studio_active rules are applied across agent layers."""
from __future__ import annotations

import re

from copilot.prompt_examples import _load_integrations, _prompt_context
from engine.mcp_nodes import (
    MCP_NODE_TYPES,
    active_mcp_node_types,
    active_mcp_tools,
    is_mcp_node_type,
)
from engine.node_availability import agent_visible_type_ids, is_agent_visible_type
from engine.registry import placeholder_specs
from engine.studio_nodes import STUDIO_APPROVED_NODE_TYPES
from generation.harness.intent import _BUILD_COMMAND
from generation.prompt_builder import PromptBuilder


def test_studio_contracts_document_omits_legacy_github() -> None:
    from engine.registry import contracts_document

    studio = contracts_document(studio_only=True)["nodes"]
    all_nodes = contracts_document(studio_only=False)["nodes"]
    assert "github" not in studio
    assert "github_mcp" in studio
    assert "github" in all_nodes
    assert STUDIO_APPROVED_NODE_TYPES == agent_visible_type_ids()


def test_inactive_integrations_not_agent_visible() -> None:
    for tid in ("outlook", "teams"):
        assert not is_agent_visible_type(tid)
    assert {s.type_id for s in placeholder_specs()} == {"outlook", "teams"}


def test_active_mcp_nodes_are_agent_visible() -> None:
    for tid in active_mcp_node_types():
        assert tid in STUDIO_APPROVED_NODE_TYPES
        assert is_mcp_node_type(tid)
    assert "mcp" not in STUDIO_APPROVED_NODE_TYPES


def test_prompt_builder_system_prompt_uses_active_mcp_nodes() -> None:
    text = PromptBuilder().system_prompt()
    for tid in active_mcp_node_types():
        assert f"`{tid}`" in text
    integrations_line = next(
        (line for line in text.splitlines() if line.strip().startswith("- Integrations:")),
        "",
    )
    assert "`outlook`" not in integrations_line
    assert "`teams`" not in integrations_line
    assert "`mcp`" not in integrations_line
    assert "Do not emit legacy combined `mcp`" in text
    assert "Never emit legacy `github` REST" in text


def test_prompt_examples_integrations_exclude_placeholders() -> None:
    integrations = _load_integrations()
    types = {i["type"] for i in integrations}
    assert "outlook" not in types
    assert "teams" not in types
    assert "jira_mcp" in types
    assert "confluence_mcp" in types


def test_prompt_examples_mcp_tools_match_registry() -> None:
    ctx = _prompt_context([], _load_integrations(), [], {})
    assert set(ctx["mcp_tools"]) == set(active_mcp_tools())


def test_harness_build_command_knows_typed_mcp_nodes() -> None:
    pattern = _BUILD_COMMAND.pattern
    for tid in active_mcp_node_types():
        assert tid in pattern
    assert "outlook" not in pattern


def test_mcp_node_types_constant_covers_legacy_and_typed() -> None:
    assert MCP_NODE_TYPES == frozenset({"mcp", "jira_mcp", "confluence_mcp", "github_mcp"})
