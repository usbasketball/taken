def test_login_success(client):
    resp = client.post("/auth/login", json={"password": "changeme"})
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert "expires_at" in data
    assert len(data["token"]) > 20


def test_login_wrong_password(client):
    resp = client.post("/auth/login", json={"password": "wrong"})
    assert resp.status_code == 401


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_protected_route_without_token(client):
    resp = client.post("/seasons", json={"name": "2025-2026"})
    assert resp.status_code == 401  # missing Authorization header


def test_protected_route_with_invalid_token(client):
    resp = client.post(
        "/seasons",
        json={"name": "2025-2026"},
        headers={"Authorization": "Bearer not-a-valid-token"},
    )
    assert resp.status_code == 401
