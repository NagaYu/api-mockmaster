"""Authentication & session tests."""


def test_register_returns_token_and_user(client):
    res = client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "password": "supersecret1"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "alice@example.com"
    assert "id" in body["user"]


def test_register_duplicate_email_conflicts(client):
    payload = {"email": "dup@example.com", "password": "supersecret1"}
    assert client.post("/api/auth/register", json=payload).status_code == 200
    assert client.post("/api/auth/register", json=payload).status_code == 409


def test_register_weak_password_rejected(client):
    res = client.post(
        "/api/auth/register", json={"email": "weak@example.com", "password": "short"}
    )
    assert res.status_code == 422


def test_register_invalid_email_rejected(client):
    res = client.post(
        "/api/auth/register", json={"email": "not-an-email", "password": "supersecret1"}
    )
    assert res.status_code == 422


def test_login_success_and_wrong_password(client):
    client.post(
        "/api/auth/register",
        json={"email": "bob@example.com", "password": "supersecret1"},
    )
    ok = client.post(
        "/api/auth/login",
        json={"email": "bob@example.com", "password": "supersecret1"},
    )
    assert ok.status_code == 200
    assert ok.json()["access_token"]

    bad = client.post(
        "/api/auth/login",
        json={"email": "bob@example.com", "password": "WRONGpassword"},
    )
    assert bad.status_code == 401


def test_login_unknown_email(client):
    res = client.post(
        "/api/auth/login",
        json={"email": "ghost@example.com", "password": "supersecret1"},
    )
    assert res.status_code == 401


def test_me_requires_and_validates_token(client, register):
    headers, user = register()
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == user["email"]


def test_management_api_requires_auth(client):
    assert client.get("/api/mocks").status_code == 403


def test_invalid_token_rejected(client):
    res = client.get("/api/mocks", headers={"Authorization": "Bearer garbage.token"})
    assert res.status_code == 401
