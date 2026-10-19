import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """User registration schema."""
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    display_name: str | None = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    """User login schema."""
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class VerifyEmailRequest(BaseModel):
    """Email verification schema."""
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=16, max_length=128)


class UserResponse(BaseModel):
    """Public authenticated user profile (whitelisted fields only)."""
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    email: str
    display_name: str | None
    role: str
    email_verified: bool
    created_at: datetime


class LoginResponse(BaseModel):
    """Login response with CSRF token and user profile."""
    model_config = ConfigDict(extra="forbid")

    user: UserResponse
    csrf_token: str
