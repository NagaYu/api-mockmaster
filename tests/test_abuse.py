"""Abuse-guard tests: quota, payload size, login rate limiting."""

import app.main as main_module


def _payload(**over):
    base = {"path": "p", "method": "GET", "response_body": "{}"}
    base.update(over)
    return base


def test_mock_quota_enforced(client, register, monkeypatch):
    monkeypatch.setattr(main_module, "MAX_MOCKS_PER_USER", 2)
    headers, _ = register()
    assert client.post("/api/mocks", json=_payload(path="a"), headers=headers).status_code == 201
    assert client.post("/api/mocks", json=_payload(path="b"), headers=headers).status_code == 201
    over = client.post("/api/mocks", json=_payload(path="c"), headers=headers)
    assert over.status_code == 403
    assert "limit" in over.json()["detail"].lower()


def test_oversized_response_rejected(client, register):
    headers, _ = register()
    big = '{"data":"' + "x" * 120_000 + '"}'
    res = client.post("/api/mocks", json=_payload(response_body=big), headers=headers)
    assert res.status_code == 422


def test_login_rate_limited(client, monkeypatch):
    monkeypatch.setattr(main_module, "LOGIN_RATE_LIMIT", 3)
    client.post(
        "/api/auth/register",
        json={"email": "rl@example.com", "password": "supersecret1"},
    )
    # register already consumed 1 attempt from this IP; a few more trip the limit.
    statuses = []
    for _ in range(6):
        r = client.post(
            "/api/auth/login",
            json={"email": "rl@example.com", "password": "supersecret1"},
        )
        statuses.append(r.status_code)
    assert 429 in statuses
