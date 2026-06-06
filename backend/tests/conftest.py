"""
Test harness setup.

We add the repository's `backend/` directory to `sys.path` so test
modules can import `engine`, `app`, `generation`, `connectors`, and
`integrations` as top-level packages — matching how the running service
imports them.

Pytest is run from the repo root (`pytest backend/tests/`) or from
`backend/` (`pytest tests/`); both work.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from runtime_env import ensure_env_loaded
ensure_env_loaded()

# Keep LLM calls out of the unit tests — anything that reaches for
# Gemini should either be mocked or skipped. Pinning the API key to
# empty makes any accidental real call fail fast.
if not os.environ.get("GEMINI_API_KEY"):
    os.environ["GEMINI_API_KEY"] = "mock_key_for_testing"


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: live Gemini harness tests (require real GEMINI_API_KEY)",
    )


import pytest
from fastapi.testclient import TestClient

from app.database import init_db
from app.main import app
from app.user_scope import SEED_PASSWORD, SEED_USER_ID, SEED_USERNAME


@pytest.fixture(scope="session")
def seed_user_id() -> str:
    return SEED_USER_ID


@pytest.fixture(autouse=True)
def _fresh_db():
    init_db()
    yield


@pytest.fixture(autouse=True)
def _seed_request_user():
    from app.request_context import set_current_user_id

    set_current_user_id(SEED_USER_ID)
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_client(client: TestClient) -> TestClient:
    response = client.post(
        "/auth/login",
        json={"username": SEED_USERNAME, "password": SEED_PASSWORD},
    )
    assert response.status_code == 200, response.text
    token = response.json().get("session_token")
    assert token
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client

