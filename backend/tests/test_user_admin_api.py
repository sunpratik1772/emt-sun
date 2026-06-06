from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def test_list_users_requires_admin(auth_client: TestClient) -> None:
    resp = auth_client.get("/user/users")
    assert resp.status_code == 200
    users = resp.json().get("users") or []
    assert any(u.get("username") == "johndoe" for u in users)
    assert any(u.get("role") == "admin" for u in users)


def test_create_user_as_admin(auth_client: TestClient) -> None:
    suffix = uuid.uuid4().hex[:8]
    payload = {
        "first_name": "Jane",
        "last_name": "Smith",
        "username": f"jane{suffix}",
        "password": "password123",
        "data_source_access": {},
        "role": "user",
    }
    created = auth_client.post("/user/users", json=payload)
    assert created.status_code == 200
    user = created.json()["user"]
    assert user["username"] == payload["username"]
    assert user["name"] == "Jane Smith"
    assert user["role"] == "user"


def test_grant_admin_role_allows_admin_endpoints(auth_client: TestClient, client: TestClient) -> None:
    suffix = uuid.uuid4().hex[:8]
    username = f"admin{suffix}"
    created = auth_client.post(
        "/user/users",
        json={
            "first_name": "Admin",
            "last_name": "User",
            "username": username,
            "password": "password123",
            "data_source_access": {},
            "role": "user",
        },
    )
    assert created.status_code == 200
    user_id = created.json()["user"]["user_id"]

    role_resp = auth_client.put(f"/user/users/{user_id}/role", json={"role": "admin"})
    assert role_resp.status_code == 200
    assert role_resp.json()["user"]["role"] == "admin"

    login = client.post("/auth/login", json={"username": username, "password": "password123"})
    assert login.status_code == 200
    token = login.json()["session_token"]
    overview = client.get("/user/admin/overview", headers={"Authorization": f"Bearer {token}"})
    assert overview.status_code == 200


def test_admin_overview(auth_client: TestClient) -> None:
    resp = auth_client.get("/user/admin/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert "totals" in body
    assert "users" in body
    assert "workflows" in body
    assert "drafts" in body
    assert "runs" in body
    assert "automations" in body
    assert body["totals"]["users"] >= 1
    assert any(u.get("counts") for u in body["users"])


def test_admin_overview_forbidden_for_non_admin(client: TestClient) -> None:
    suffix = uuid.uuid4().hex[:8]
    username = f"plain{suffix}"
    auth_client = client
    login_admin = auth_client.post(
        "/auth/login",
        json={"username": "johndoe", "password": "password123"},
    )
    assert login_admin.status_code == 200
    admin_token = login_admin.json()["session_token"]
    created = auth_client.post(
        "/user/users",
        json={
            "first_name": "Plain",
            "last_name": "User",
            "username": username,
            "password": "password123",
            "data_source_access": {},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert created.status_code == 200

    login = client.post("/auth/login", json={"username": username, "password": "password123"})
    assert login.status_code == 200
    token = login.json()["session_token"]
    resp = client.get("/user/admin/overview", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_delete_user(auth_client: TestClient) -> None:
    suffix = uuid.uuid4().hex[:8]
    username = f"del{suffix}"
    created = auth_client.post(
        "/user/users",
        json={
            "first_name": "Delete",
            "last_name": "Me",
            "username": username,
            "password": "password123",
            "data_source_access": {},
        },
    )
    assert created.status_code == 200
    user_id = created.json()["user"]["user_id"]

    deleted = auth_client.delete(f"/user/users/{user_id}")
    assert deleted.status_code == 200

    login = auth_client.post(
        "/auth/login",
        json={"username": username, "password": "password123"},
    )
    assert login.status_code == 401


def test_skill_and_feature_access(auth_client: TestClient) -> None:
    suffix = uuid.uuid4().hex[:8]
    created = auth_client.post(
        "/user/users",
        json={
            "first_name": "Scoped",
            "last_name": "User",
            "username": f"scoped{suffix}",
            "password": "password123",
            "data_source_access": {},
            "skill_access": {},
            "feature_access": {"run_history": False},
        },
    )
    assert created.status_code == 200
    user_id = created.json()["user"]["user_id"]

    features = auth_client.get(f"/user/users/{user_id}/feature-access")
    assert features.status_code == 200
    run_row = next(f for f in features.json()["features"] if f["feature_key"] == "run_history")
    assert run_row["enabled"] is False

    auth_client.put(f"/user/users/{user_id}/feature-access/run_history", json={"enabled": True})
    login = auth_client.post(
        "/auth/login",
        json={"username": f"scoped{suffix}", "password": "password123"},
    )
    assert login.status_code == 200
    token = login.json()["session_token"]
    logs = auth_client.get("/run-logs", headers={"Authorization": f"Bearer {token}"})
    assert logs.status_code == 200


def test_create_user_forbidden_for_non_admin(client: TestClient) -> None:
    suffix = uuid.uuid4().hex[:8]
    login = client.post(
        "/auth/login",
        json={"username": "johndoe", "password": "password123"},
    )
    assert login.status_code == 200
    admin_token = login.json()["session_token"]
    created = client.post(
        "/user/users",
        json={
            "first_name": "Jane",
            "last_name": "Smith",
            "username": f"jane{suffix}",
            "password": "password123",
            "data_source_access": {},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert created.status_code == 200

    user_login = client.post(
        "/auth/login",
        json={"username": f"jane{suffix}", "password": "password123"},
    )
    assert user_login.status_code == 200
    token = user_login.json()["session_token"]
    resp = client.post(
        "/user/users",
        json={
            "first_name": "Blocked",
            "last_name": "User",
            "username": f"blocked{suffix}",
            "password": "password123",
            "data_source_access": {},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
