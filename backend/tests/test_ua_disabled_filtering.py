"""Tests that CodebaseAnalyzer ignores inactive/disabled/placeholder node spec files."""
from __future__ import annotations

import os
from pathlib import Path
from app.code_graph_analyzer import CodebaseAnalyzer
from app.understand_anything import generate_knowledge_graph, generate_domain_graph
from engine.registry import all_specs, placeholder_specs


def test_codebase_analyzer_ignores_inactive_nodes():
    # Run analysis using CodebaseAnalyzer on backend directory
    backend_dir = Path(__file__).resolve().parents[2] / "backend"
    analyzer = CodebaseAnalyzer(str(backend_dir))
    
    # Assert should_ignore rules
    # Enabled/active specs should NOT be ignored
    active_types = [s.type_id for s in all_specs()]
    for atype in active_types:
        if atype not in ("__init__", "mcp_common"):
            path = backend_dir / "engine" / "nodes" / f"{atype}.py"
            assert not analyzer.should_ignore(path), f"Active spec {atype} was ignored!"

    # Placeholder/legacy specs should be ignored
    from engine.registry import _SPECS_ALL, _SPECS_STUDIO
    active_set = {s.type_id for s in _SPECS_STUDIO}
    legacy_types = [s.type_id for s in _SPECS_ALL if s.type_id not in active_set]
    
    for itype in legacy_types:
        if itype not in ("__init__", "mcp_common"):
            path = backend_dir / "engine" / "nodes" / f"{itype}.py"
            yaml_path = backend_dir / "engine" / "nodes" / f"{itype}.yaml"
            assert analyzer.should_ignore(path), f"Inactive spec {itype} was not ignored!"
            assert analyzer.should_ignore(yaml_path), f"Inactive yaml for {itype} was not ignored!"


def test_generated_graphs_do_not_contain_inactive_nodes():
    # Run analysis
    backend_dir = Path(__file__).resolve().parents[2] / "backend"
    project_root = backend_dir.parent
    
    knowledge_graph = generate_knowledge_graph(root=project_root)
    nodes = knowledge_graph.get("nodes", [])
    
    # Check that no node ID has a path containing inactive node files
    from engine.registry import _SPECS_ALL, _SPECS_STUDIO
    active_set = {s.type_id for s in _SPECS_STUDIO}
    legacy_types = [s.type_id for s in _SPECS_ALL if s.type_id not in active_set]
    
    for node in nodes:
        node_id = str(node.get("id"))
        file_path = str(node.get("filePath") or "")
        
        # Check if the node is linked to any of the inactive types
        for itype in legacy_types:
            assert f"nodes/{itype}.py" not in file_path, f"Found inactive spec {itype} file in graph: {file_path}"
            assert f"nodes/{itype}.yaml" not in file_path, f"Found inactive spec {itype} yaml in graph: {file_path}"
            assert f"nodes/{itype}:" not in node_id, f"Found inactive spec {itype} in node ID: {node_id}"
