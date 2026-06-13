"""
API Mockmaster — FastAPI application entrypoint.

Responsibilities:
  * Serve the single-page dashboard.
  * Authenticate users (register / login, JWT).
  * Expose an owner-scoped CRUD API for managing mocks (/api/mocks).
  * Dynamically serve user-defined fake endpoints (/mock/{mock_id}/{path}).
  * Apply bullet-proof CORS so any frontend dev server can call the mocks.
  * Guard against abuse (per-user quota, payload caps, login rate limiting).
"""

import asyncio
import json
import os
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Deque, Dict, List

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app import auth, models, schemas
from app.database import get_db, init_db

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"

# Abuse guards (configurable per deployment).
MAX_MOCKS_PER_USER = int(os.getenv("MAX_MOCKS_PER_USER", "200"))
LOGIN_RATE_LIMIT = int(os.getenv("LOGIN_RATE_LIMIT", "10"))  # attempts
LOGIN_RATE_WINDOW = int(os.getenv("LOGIN_RATE_WINDOW", "60"))  # seconds


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dev convenience: auto-create tables so `uvicorn app.main:app` just works.
    # In production, manage schema with Alembic (`alembic upgrade head`) and set
    # AUTO_CREATE_TABLES=0 so migrations are the single source of truth.
    if os.getenv("AUTO_CREATE_TABLES", "1") == "1":
        init_db()
    if auth._USING_EPHEMERAL_KEY:
        print(
            "⚠️  SECRET_KEY is not set — using an ephemeral key. "
            "Sessions will reset on restart. Set SECRET_KEY in production."
        )
    yield


app = FastAPI(
    title="API Mockmaster",
    version="1.0.0",
    description="Generate fake API endpoints in one second.",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — wide open by design. These mocks exist to be hit from any localhost
# dev server (3000 / 5173 / 8080 / …) without a single preflight failure.
# allow_credentials must be False when origins is "*" (CORS spec requirement);
# auth uses a Bearer token header, not cookies, so this is correct.
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400,
)

DYNAMIC_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]

# ---------------------------------------------------------------------------
# Tiny in-memory rate limiter for auth endpoints.
# NOTE: per-process only. For multi-worker / multi-instance production, back
# this with Redis. It is here to blunt credential-stuffing on a single box.
# ---------------------------------------------------------------------------
_login_hits: Dict[str, Deque[float]] = defaultdict(deque)


def _rate_limit_login(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    hits = _login_hits[ip]
    while hits and now - hits[0] > LOGIN_RATE_WINDOW:
        hits.popleft()
    if len(hits) >= LOGIN_RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Too many attempts. Please wait a minute and try again.",
        )
    hits.append(now)


# ===========================================================================
# Dashboard
# ===========================================================================
@app.get("/", include_in_schema=False)
async def dashboard() -> FileResponse:
    return FileResponse(TEMPLATES_DIR / "index.html")


@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict:
    return {"status": "ok"}


# ===========================================================================
# Auth
# ===========================================================================
@app.post("/api/auth/register", response_model=schemas.TokenOut, tags=["auth"])
def register(payload: schemas.UserCreate, request: Request, db: Session = Depends(get_db)):
    _rate_limit_login(request)
    email = payload.email.lower().strip()
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    user = models.User(email=email, password_hash=auth.hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return schemas.TokenOut(access_token=auth.create_access_token(user.id), user=user)


@app.post("/api/auth/login", response_model=schemas.TokenOut, tags=["auth"])
def login(payload: schemas.UserLogin, request: Request, db: Session = Depends(get_db)):
    _rate_limit_login(request)
    email = payload.email.lower().strip()
    user = db.query(models.User).filter(models.User.email == email).first()
    # Constant-ish failure path: same error whether the email or password is wrong.
    if not user or not auth.verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return schemas.TokenOut(access_token=auth.create_access_token(user.id), user=user)


@app.get("/api/auth/me", response_model=schemas.UserOut, tags=["auth"])
def me(current: models.User = Depends(auth.get_current_user)):
    return current


# ===========================================================================
# Management API (CRUD) — owner-scoped
# ===========================================================================
@app.get("/api/mocks", response_model=List[schemas.MockOut], tags=["mocks"])
def list_mocks(
    db: Session = Depends(get_db),
    current: models.User = Depends(auth.get_current_user),
):
    return (
        db.query(models.MockEndpoint)
        .filter(models.MockEndpoint.owner_id == current.id)
        .order_by(models.MockEndpoint.created_at.desc())
        .all()
    )


@app.post("/api/mocks", response_model=schemas.MockOut, status_code=201, tags=["mocks"])
def create_mock(
    payload: schemas.MockCreate,
    db: Session = Depends(get_db),
    current: models.User = Depends(auth.get_current_user),
):
    count = (
        db.query(models.MockEndpoint)
        .filter(models.MockEndpoint.owner_id == current.id)
        .count()
    )
    if count >= MAX_MOCKS_PER_USER:
        raise HTTPException(
            status_code=403,
            detail=f"Mock limit reached ({MAX_MOCKS_PER_USER}). Delete some to add more.",
        )
    mock = models.MockEndpoint(
        owner_id=current.id,
        path=payload.path,
        method=payload.method,
        response_body=payload.response_body,
        status_code=payload.status_code,
        delay_ms=payload.delay_ms,
    )
    db.add(mock)
    db.commit()
    db.refresh(mock)
    return mock


def _owned_mock_or_404(mock_id: str, current: models.User, db: Session) -> models.MockEndpoint:
    mock = db.get(models.MockEndpoint, mock_id)
    if not mock or mock.owner_id != current.id:
        # Same 404 whether it doesn't exist or belongs to someone else — no leak.
        raise HTTPException(status_code=404, detail="Mock not found")
    return mock


@app.get("/api/mocks/{mock_id}", response_model=schemas.MockOut, tags=["mocks"])
def get_mock(
    mock_id: str,
    db: Session = Depends(get_db),
    current: models.User = Depends(auth.get_current_user),
):
    return _owned_mock_or_404(mock_id, current, db)


@app.put("/api/mocks/{mock_id}", response_model=schemas.MockOut, tags=["mocks"])
def update_mock(
    mock_id: str,
    payload: schemas.MockUpdate,
    db: Session = Depends(get_db),
    current: models.User = Depends(auth.get_current_user),
):
    mock = _owned_mock_or_404(mock_id, current, db)
    mock.path = payload.path
    mock.method = payload.method
    mock.response_body = payload.response_body
    mock.status_code = payload.status_code
    mock.delay_ms = payload.delay_ms
    db.commit()
    db.refresh(mock)
    return mock


@app.delete("/api/mocks/{mock_id}", status_code=204, tags=["mocks"])
def delete_mock(
    mock_id: str,
    db: Session = Depends(get_db),
    current: models.User = Depends(auth.get_current_user),
):
    mock = _owned_mock_or_404(mock_id, current, db)
    db.delete(mock)
    db.commit()
    return Response(status_code=204)


# ===========================================================================
# Dynamic mock serving — PUBLIC (no auth, that's the point)
# ===========================================================================
async def _serve_mock(mock_id: str, target_path: str, request: Request, db: Session):
    """Look up a mock by id + method, optionally delay, then return its body."""
    mock = db.get(models.MockEndpoint, mock_id)
    if not mock:
        return JSONResponse(
            status_code=404,
            content={
                "error": "mock_not_found",
                "detail": f"No mock endpoint exists for id '{mock_id}'.",
            },
        )

    if mock.method != request.method:
        return JSONResponse(
            status_code=405,
            content={
                "error": "method_not_allowed",
                "detail": f"This mock only responds to {mock.method}.",
                "allowed_method": mock.method,
            },
            headers={"Allow": mock.method},
        )

    if mock.delay_ms and mock.delay_ms > 0:
        await asyncio.sleep(mock.delay_ms / 1000.0)

    try:
        content = json.loads(mock.response_body) if mock.response_body else {}
    except (json.JSONDecodeError, ValueError):
        return Response(
            content=mock.response_body,
            status_code=mock.status_code,
            media_type="application/json",
        )

    return JSONResponse(status_code=mock.status_code, content=content)


@app.api_route("/mock/{mock_id}", methods=DYNAMIC_METHODS, include_in_schema=False)
async def serve_mock_root(mock_id: str, request: Request, db: Session = Depends(get_db)):
    return await _serve_mock(mock_id, "", request, db)


@app.api_route(
    "/mock/{mock_id}/{target_path:path}", methods=DYNAMIC_METHODS, include_in_schema=False
)
async def serve_mock(
    mock_id: str, target_path: str, request: Request, db: Session = Depends(get_db)
):
    return await _serve_mock(mock_id, target_path, request, db)
