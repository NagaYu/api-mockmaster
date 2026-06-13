"""Shared pytest fixtures: isolated DB + dependency overrides + helpers."""

import os
import tempfile

# Deterministic signing key so JWTs are stable across the test session.
os.environ.setdefault("SECRET_KEY", "test-secret-key")
# Tests manage the schema themselves; don't double-create on import side effects.
os.environ.setdefault("AUTO_CREATE_TABLES", "0")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.main as main_module
from app.database import Base, get_db
from app.main import app


@pytest.fixture(scope="session")
def _engine():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(
        f"sqlite:///{path}", connect_args={"check_same_thread": False}, future=True
    )
    yield engine
    engine.dispose()
    os.remove(path)


@pytest.fixture(scope="session")
def _SessionLocal(_engine):
    return sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture(autouse=True)
def _isolated_db(_engine, _SessionLocal):
    """Fresh schema + clean rate-limiter for every test."""
    Base.metadata.drop_all(bind=_engine)
    Base.metadata.create_all(bind=_engine)
    main_module._login_hits.clear()

    def _override_get_db():
        db = _SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def register(client):
    """Register a user and return (auth_headers, user_json)."""

    def _register(email="user@example.com", password="supersecret1"):
        res = client.post(
            "/api/auth/register", json={"email": email, "password": password}
        )
        assert res.status_code == 200, res.text
        body = res.json()
        return {"Authorization": f"Bearer {body['access_token']}"}, body["user"]

    return _register
