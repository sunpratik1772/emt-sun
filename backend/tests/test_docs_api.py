from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_docs_api_lists_all_guides(client: TestClient) -> None:
    response = client.get("/api/docs")
    assert response.status_code == 200
    sections = response.json()["sections"]
    assert sections[0]["id"] == "guides"
    ids = {item["id"] for item in sections[0]["items"]}
    assert "frontend-architecture" in ids
    assert "database" in ids
    assert len(ids) == 10


def test_each_guide_has_content(client: TestClient) -> None:
    response = client.get("/api/docs")
    for item in response.json()["sections"][0]["items"]:
        assert item["content"].strip(), item["id"]
        assert item["title"]
