"""
Database connection layer.

Defaults to a zero-config local SQLite file so the product runs with a single
command. To switch to PostgreSQL (or any other SQLAlchemy-supported engine) in
production, just set the DATABASE_URL environment variable, e.g.:

    export DATABASE_URL="postgresql+psycopg://user:pass@host:5432/mockmaster"

No code change is required — the engine is built from that URL at boot.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# ---------------------------------------------------------------------------
# Engine configuration
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./mockmaster.db")

# `check_same_thread` is a SQLite-only quirk; we only pass it for SQLite so the
# same config works unchanged against PostgreSQL/MySQL/etc.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,  # transparently recover stale connections (matters for Postgres)
    future=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a scoped DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables on startup if they do not yet exist."""
    # Import models so they are registered on the metadata before create_all.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
