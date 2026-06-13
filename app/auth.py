"""
Authentication: password hashing (bcrypt) + stateless JWT sessions.

Design notes for a commercial deployment:
  * SECRET_KEY MUST be set in production. The dev fallback is randomised per
    process so tokens never silently work across an accidental prod restart
    with a default key — it forces you to configure it.
  * Tokens are short-lived bearer JWTs stored client-side; mocks themselves
    stay public (no auth) so any frontend can hit them — only the *management*
    API is protected.
"""

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app import models
from app.database import get_db

ALGORITHM = "HS256"
ACCESS_TOKEN_TTL_HOURS = int(os.getenv("ACCESS_TOKEN_TTL_HOURS", "168"))  # 7 days

# In production set a long random SECRET_KEY (e.g. `openssl rand -hex 32`).
# Without it, tokens are invalidated on every restart — safe, but not for prod.
SECRET_KEY = os.getenv("SECRET_KEY") or os.urandom(32).hex()
_USING_EPHEMERAL_KEY = "SECRET_KEY" not in os.environ

_bearer = HTTPBearer(auto_error=True)


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    # bcrypt operates on bytes and silently truncates >72 bytes; guard explicitly.
    pw = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8")[:72], password_hash.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------
def create_access_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(hours=ACCESS_TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _decode_token(token: str) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired"
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )
    return sub


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------
def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> models.User:
    user_id = _decode_token(creds.credentials)
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found"
        )
    return user
