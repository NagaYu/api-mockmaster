"""CRUD + multi-tenancy tests for the management API."""


def _make_payload(**over):
    base = {
        "path": "api/v1/posts",
        "method": "GET",
        "response_body": '{"hello":"world"}',
        "status_code": 200,
        "delay_ms": 0,
    }
    base.update(over)
    return base


def test_create_and_list_scoped_to_owner(client, register):
    headers, _ = register()
    res = client.post("/api/mocks", json=_make_payload(), headers=headers)
    assert res.status_code == 201
    mock = res.json()
    assert mock["id"]
    assert mock["path"] == "api/v1/posts"

    listed = client.get("/api/mocks", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_path_leading_slash_normalized(client, register):
    headers, _ = register()
    res = client.post("/api/mocks", json=_make_payload(path="/api/v1/x"), headers=headers)
    assert res.json()["path"] == "api/v1/x"


def test_update_mock(client, register):
    headers, _ = register()
    mid = client.post("/api/mocks", json=_make_payload(), headers=headers).json()["id"]
    res = client.put(
        f"/api/mocks/{mid}",
        json=_make_payload(response_body='{"updated":true}', status_code=201),
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["status_code"] == 201


def test_delete_mock(client, register):
    headers, _ = register()
    mid = client.post("/api/mocks", json=_make_payload(), headers=headers).json()["id"]
    assert client.delete(f"/api/mocks/{mid}", headers=headers).status_code == 204
    assert client.get(f"/api/mocks/{mid}", headers=headers).status_code == 404


def test_invalid_method_rejected(client, register):
    headers, _ = register()
    res = client.post("/api/mocks", json=_make_payload(method="FETCH"), headers=headers)
    assert res.status_code == 422


def test_broken_json_rejected(client, register):
    headers, _ = register()
    res = client.post(
        "/api/mocks", json=_make_payload(response_body="{bad,,,}"), headers=headers
    )
    assert res.status_code == 422


def test_tenants_are_isolated(client, register):
    alice_h, _ = register(email="alice@example.com")
    bob_h, _ = register(email="bob@example.com")

    mid = client.post("/api/mocks", json=_make_payload(), headers=alice_h).json()["id"]

    # Bob cannot see Alice's mocks.
    assert client.get("/api/mocks", headers=bob_h).json() == []
    # Bob gets a 404 (no existence leak) reading or deleting Alice's mock.
    assert client.get(f"/api/mocks/{mid}", headers=bob_h).status_code == 404
    assert client.delete(f"/api/mocks/{mid}", headers=bob_h).status_code == 404
    # Alice still has it.
    assert len(client.get("/api/mocks", headers=alice_h).json()) == 1
