from __future__ import annotations

from fastapi.testclient import TestClient

from app.user_scope import SEED_USER_ID


def test_data_source_access_toggle(auth_client: TestClient) -> None:
    resp = auth_client.get("/user/data-source-access")
    assert resp.status_code == 200
    sources = resp.json().get("sources") or []
    assert len(sources) >= 1
    source_id = sources[0]["source_id"]

    off = auth_client.put(f"/user/data-source-access/{source_id}", json={"has_access": False})
    assert off.status_code == 200
    assert off.json()["has_access"] is False

    listed = auth_client.get("/user/data-source-access")
    row = next(s for s in listed.json()["sources"] if s["source_id"] == source_id)
    assert row["has_access"] is False

    on = auth_client.put(f"/user/data-source-access/{source_id}", json={"has_access": True})
    assert on.status_code == 200


def test_good_example_prefs(auth_client: TestClient) -> None:
    resp = auth_client.get("/user/preferences/good-examples")
    assert resp.status_code == 200
    body = resp.json()
    assert "promote_to_folder" in body
    assert "promote_to_table" in body

    updated = auth_client.put(
        "/user/preferences/good-examples",
        json={"promote_to_folder": False, "promote_to_table": True},
    )
    assert updated.status_code == 200
    assert updated.json()["promote_to_folder"] is False
    assert updated.json()["promote_to_table"] is True
