"""SQLAlchemy ORM models."""

import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


def generate_mock_id() -> str:
    """Short, URL-safe, collision-resistant public identifier (e.g. 'a1b2c3d4e5')."""
    # 8 random bytes -> ~16 hex chars; short enough to read, big enough to be unique.
    return secrets.token_hex(5)


def generate_uuid() -> str:
    return uuid.uuid4().hex


class User(Base):
    """A registered account that owns mock endpoints (multi-tenancy)."""

    __tablename__ = "users"

    id = Column(String(32), primary_key=True, default=generate_uuid)
    email = Column(String(320), nullable=False, unique=True, index=True)
    password_hash = Column(String(128), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    mocks = relationship(
        "MockEndpoint",
        back_populates="owner",
        cascade="all, delete-orphan",
    )


class MockEndpoint(Base):
    """A single user-defined fake API endpoint."""

    __tablename__ = "mock_endpoints"

    # Public, URL-facing id. Random short hash, also the primary key.
    id = Column(String(32), primary_key=True, default=generate_mock_id, index=True)

    # Tenant ownership.
    owner_id = Column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Request matchers.
    path = Column(String(2048), nullable=False, default="", index=True)
    method = Column(String(10), nullable=False, default="GET", index=True)

    # Response definition.
    response_body = Column(Text, nullable=False, default="{}")
    status_code = Column(Integer, nullable=False, default=200)
    delay_ms = Column(Integer, nullable=False, default=0)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    owner = relationship("User", back_populates="mocks")
