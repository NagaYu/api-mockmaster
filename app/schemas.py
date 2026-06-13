"""Pydantic request/response schemas with strict JSON validation."""

import json
import os
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}

# Abuse guard: cap stored response size so the service can't be used as free
# blob storage. Configurable per deployment.
MAX_RESPONSE_BYTES = int(os.getenv("MAX_RESPONSE_BYTES", str(100 * 1024)))  # 100 KB


# ===========================================================================
# Auth
# ===========================================================================
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: str
    email: EmailStr
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ===========================================================================
# Mocks
# ===========================================================================
class MockBase(BaseModel):
    path: str = Field(default="", max_length=2048, description="e.g. api/v1/posts")
    method: str = Field(default="GET")
    response_body: str = Field(default="{}", description="Raw JSON string")
    status_code: int = Field(default=200, ge=100, le=599)
    delay_ms: int = Field(default=0, ge=0, le=60000)

    @field_validator("method")
    @classmethod
    def _normalize_method(cls, v: str) -> str:
        v = (v or "GET").strip().upper()
        if v not in ALLOWED_METHODS:
            raise ValueError(
                f"method must be one of {sorted(ALLOWED_METHODS)}, got '{v}'"
            )
        return v

    @field_validator("path")
    @classmethod
    def _normalize_path(cls, v: str) -> str:
        # Store paths without a leading slash so '/mock/{id}/{path}' concatenation
        # is unambiguous. '/api/v1/posts' and 'api/v1/posts' are treated the same.
        return (v or "").strip().lstrip("/")

    @field_validator("response_body")
    @classmethod
    def _validate_json(cls, v: str) -> str:
        """Backend safety net: reject broken / oversized JSON before it is stored."""
        if v is None or v.strip() == "":
            return "{}"
        if len(v.encode("utf-8")) > MAX_RESPONSE_BYTES:
            raise ValueError(
                f"response_body exceeds the {MAX_RESPONSE_BYTES // 1024} KB limit"
            )
        try:
            json.loads(v)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"response_body is not valid JSON: {exc}") from exc
        return v


class MockCreate(MockBase):
    pass


class MockUpdate(MockBase):
    pass


class MockOut(MockBase):
    id: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
