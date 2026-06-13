"""Dynamic public mock-serving tests."""

import time


def _create(client, headers, **over):
    payload = {
        "path": "api/v1/posts",
        "method": "GET",
        "response_body": '{"hello":"world"}',
        "status_code": 200,
        "delay_ms": 0,
    }
    payload.update(over)
    return client.post("/api/mocks", json=payload, headers=headers).json()


def test_serve_returns_stored_body_publicly(client, register):
    headers, _ = register()
    mock = _create(client, headers)
    # No auth header on the serve call — mocks are public.
    res = client.get(f"/mock/{mock['id']}/api/v1/posts")
    assert res.status_code == 200
    assert res.json() == {"hello": "world"}
    assert res.headers["content-type"].startswith("application/json")


def test_serve_custom_status_code(client, register):
    headers, _ = register()
    mock = _create(client, headers, response_body='{"error":"nope"}', status_code=404)
    res = client.get(f"/mock/{mock['id']}/api/v1/posts")
    assert res.status_code == 404
    assert res.json() == {"error": "nope"}


def test_serve_wrong_method_405(client, register):
    headers, _ = register()
    mock = _create(client, headers, method="GET")
    res = client.post(f"/mock/{mock['id']}/api/v1/posts")
    assert res.status_code == 405
    assert res.headers.get("Allow") == "GET"


def test_serve_unknown_id_404(client):
    res = client.get("/mock/doesnotexist/whatever")
    assert res.status_code == 404
    assert res.json()["error"] == "mock_not_found"


def test_serve_respects_delay(client, register):
    headers, _ = register()
    mock = _create(client, headers, delay_ms=300)
    start = time.monotonic()
    res = client.get(f"/mock/{mock['id']}/api/v1/posts")
    elapsed = time.monotonic() - start
    assert res.status_code == 200
    assert elapsed >= 0.28  # ~300ms, allow scheduling slack


def test_serve_post_mock(client, register):
    headers, _ = register()
    mock = _create(client, headers, path="api/login", method="POST",
                   response_body='{"token":"abc"}', status_code=201)
    res = client.post(f"/mock/{mock['id']}/api/login", json={"user": "x"})
    assert res.status_code == 201
    assert res.json() == {"token": "abc"}
