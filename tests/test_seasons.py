def test_list_seasons_empty(client):
    resp = client.get("/seasons")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_season(client, auth_headers):
    resp = client.post("/seasons", json={"name": "2025-2026"}, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "2025-2026"
    assert "created_at" in data


def test_create_season_invalid_name(client, auth_headers):
    resp = client.post("/seasons", json={"name": "2025"}, headers=auth_headers)
    assert resp.status_code == 422

    resp = client.post("/seasons", json={"name": "current"}, headers=auth_headers)
    assert resp.status_code == 422


def test_create_season_duplicate(client, auth_headers):
    client.post("/seasons", json={"name": "2025-2026"}, headers=auth_headers)
    resp = client.post("/seasons", json={"name": "2025-2026"}, headers=auth_headers)
    assert resp.status_code == 409


def test_create_season_requires_auth(client):
    resp = client.post("/seasons", json={"name": "2025-2026"})
    assert resp.status_code == 401


def test_get_season(client, auth_headers):
    client.post("/seasons", json={"name": "2025-2026"}, headers=auth_headers)
    resp = client.get("/seasons/2025-2026")
    assert resp.status_code == 200
    assert resp.json()["name"] == "2025-2026"


def test_get_season_not_found(client):
    resp = client.get("/seasons/2099-2100")
    assert resp.status_code == 404


def test_delete_season(client, auth_headers):
    client.post("/seasons", json={"name": "2025-2026"}, headers=auth_headers)
    resp = client.delete("/seasons/2025-2026", headers=auth_headers)
    assert resp.status_code == 204
    assert client.get("/seasons/2025-2026").status_code == 404


def test_delete_season_not_found(client, auth_headers):
    resp = client.delete("/seasons/2099-2100", headers=auth_headers)
    assert resp.status_code == 404
