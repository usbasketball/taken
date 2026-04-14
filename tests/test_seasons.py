def test_list_seasons_empty(client):
    resp = client.get("/seasons")
    assert resp.status_code == 200
    assert resp.json() == []


def test_active_season_none(client):
    resp = client.get("/seasons/active")
    assert resp.status_code == 200
    assert resp.json() is None


def test_create_season(client, auth_headers):
    resp = client.post("/seasons", json={"name": "2025-2026"}, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "2025-2026"
    assert data["is_active"] is False
    assert data["is_published"] is False
    assert "id" in data


def test_create_season_requires_auth(client):
    resp = client.post("/seasons", json={"name": "2025-2026"})
    assert resp.status_code == 403


def test_get_season(client, auth_headers):
    created = client.post("/seasons", json={"name": "2025-2026"}, headers=auth_headers).json()
    resp = client.get(f"/seasons/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "2025-2026"


def test_get_season_not_found(client):
    resp = client.get("/seasons/9999")
    assert resp.status_code == 404


def test_activate_season(client, auth_headers):
    s1 = client.post("/seasons", json={"name": "2024-2025"}, headers=auth_headers).json()
    s2 = client.post("/seasons", json={"name": "2025-2026"}, headers=auth_headers).json()

    # Activate s1
    resp = client.put(f"/seasons/{s1['id']}", json={"is_active": True}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True

    # Activating s2 should deactivate s1
    client.put(f"/seasons/{s2['id']}", json={"is_active": True}, headers=auth_headers)
    assert client.get(f"/seasons/{s1['id']}").json()["is_active"] is False
    assert client.get(f"/seasons/{s2['id']}").json()["is_active"] is True

    # GET /seasons/active should return s2
    active = client.get("/seasons/active").json()
    assert active["id"] == s2["id"]


def test_delete_season(client, auth_headers):
    s = client.post("/seasons", json={"name": "2025-2026"}, headers=auth_headers).json()
    resp = client.delete(f"/seasons/{s['id']}", headers=auth_headers)
    assert resp.status_code == 204
    assert client.get(f"/seasons/{s['id']}").status_code == 404


def test_cannot_delete_active_season(client, auth_headers):
    s = client.post("/seasons", json={"name": "2025-2026"}, headers=auth_headers).json()
    client.put(f"/seasons/{s['id']}", json={"is_active": True}, headers=auth_headers)
    resp = client.delete(f"/seasons/{s['id']}", headers=auth_headers)
    assert resp.status_code == 400
