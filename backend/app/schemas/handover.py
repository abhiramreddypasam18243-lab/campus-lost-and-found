"""Pydantic schemas for handover verification and code reissue (spec section 5.4, AC-86 to AC-96)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HandoverVerificationRequest(BaseModel):
    """Schema for moderator code verification at handover desk (AC-90, AC-93)."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=4, max_length=32)
    identity_note: str = Field(..., min_length=10, max_length=2000)


class HandoverReissueRequest(BaseModel):
    """Schema for moderator code reissue (AC-92)."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=10, max_length=2000)


class HandoverStatusResponse(BaseModel):
    """Handover desk status view for staff (AC-96: NEVER exposes plaintext code or HMAC)."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    claim_id: uuid.UUID
    status: str
    attempts: int
    max_attempts: int
    attempts_left: int
    reissue_count: int
    max_reissues: int
    issued_at: datetime
    expires_at: datetime
    is_expired: bool = False
    is_locked: bool = False


class HandoverVerifyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    claim_id: uuid.UUID
    found_id: uuid.UUID
    status: str
    message: str
