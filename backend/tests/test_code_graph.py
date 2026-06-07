from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client() -> TestClient:
    return TestClient(app)

def test_code_graph_json_endpoint(client: TestClient) -> None:
    response = client.get("/api/code-graph")
    assert response.status_code == 200
    
    data = response.json()
    assert "project" in data
    assert "nodes" in data
    assert "edges" in data
    
    # Verify project meta
    project = data["project"]
    assert project["name"] == "emt-sun"
    assert "languages" in project
    assert "analyzedAt" in project
    
    # Verify nodes structure
    nodes = data["nodes"]
    assert len(nodes) > 0
    first_node = nodes[0]
    assert "id" in first_node
    assert "type" in first_node
    assert "name" in first_node
    
    # Verify node types exist
    types = {n["type"] for n in nodes}
    assert "file" in types
    # Since we have Python files in the workspace, we should have function and class/endpoint nodes
    assert "function" in types or "class" in types
    
    # Verify edges
    edges = data["edges"]
    assert len(edges) > 0
    first_edge = edges[0]
    assert "source" in first_edge
    assert "target" in first_edge
    assert "type" in first_edge

def test_code_graph_view_endpoint(client: TestClient) -> None:
    response = client.get("/api/code-graph/view")
    assert response.status_code == 200
    
    # Verify it returns HTML and contains key visual elements
    html = response.text
    assert "<!DOCTYPE html>" in html
    assert "vis-network.min.js" in html
    assert "network-container" in html
    assert "details-panel" in html
    assert "search-select" in html
