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
    """Email verification schema by token or 6-digit numeric code."""

    model_config = ConfigDict(extra="forbid")

    token: str | None = Field(default=None, min_length=4, max_length=128)
    code: str | None = Field(default=None, min_length=4, max_length=128)


class RegisterResponse(BaseModel):
    """Registration response."""

    model_config = ConfigDict(extra="forbid")

    message: str
    email: str
    verified: bool = False


class ResendVerificationResponse(BaseModel):
    """Resend email verification response."""

    model_config = ConfigDict(extra="forbid")

    message: str


class UserResponse(BaseModel):
    """Public authenticated user profile (whitelisted fields only)."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    email: str
    display_name: str | None
    role: str
    email_verified: bool
    notify_match_email: bool = True
    created_at: datetime


class UpdateMeRequest(BaseModel):
    """Profile fields a user may change themselves (P3: no other personal data)."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, max_length=100)
    notify_match_email: bool | None = None


class CsrfResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    csrf_token: str


class LoginResponse(BaseModel):
    """Login response with CSRF token and user profile."""

    model_config = ConfigDict(extra="forbid")

    user: UserResponse
    csrf_token: str
