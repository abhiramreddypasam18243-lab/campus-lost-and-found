"""Pydantic schemas for claims and moderation (AC-75 to AC-85)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ClaimCreate(BaseModel):
    """Schema for submitting a claim on a found item (AC-75)."""

    model_config = ConfigDict(extra="forbid")

    found_id: uuid.UUID
    lost_id: uuid.UUID | None = None
    evidence: str = Field(..., min_length=20, max_length=2000)
    answers: dict[str, str] = Field(default_factory=dict)
    image_ids: list[uuid.UUID] = Field(default_factory=list, max_length=3)


class ClaimEvidenceUpdate(BaseModel):
    """Schema for resubmitting evidence when needs_more_info (AC-82)."""

    model_config = ConfigDict(extra="forbid")

    evidence: str = Field(..., min_length=20, max_length=2000)
    answers: dict[str, str] | None = None
    image_ids: list[uuid.UUID] | None = None


class ClaimDecisionRequest(BaseModel):
    """Schema for moderator decision notes (AC-79). Minimum 10 characters."""

    model_config = ConfigDict(extra="forbid")

    decision_note: str = Field(..., min_length=10, max_length=2000)


class ClaimResponse(BaseModel):
    """Detailed claim view for claimant and moderators (AC-77)."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    found_id: uuid.UUID
    lost_id: uuid.UUID | None
    claimant_id: uuid.UUID
    evidence: str
    answers: dict[str, Any]
    image_ids: list[Any]
    status: str
    decision_note: str | None = None
    reviewer_id: uuid.UUID | None = None
    locked_by_id: uuid.UUID | None = None
    lock_expires_at: datetime | None = None
    submitted_at: datetime
    reviewed_at: datetime | None = None
    escalated: bool = False
    handover_code: str | None = None
    found_title: str | None = None
    created_at: datetime


class ModeratorQueueItem(BaseModel):
    """Unified item in the moderator review queue (AC-78, AC-84, AC-85)."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    item_type: str  # "claim", "report", "duplicate_image"
    title: str
    status: str
    submitted_at: datetime
    escalated: bool = False
    locked_by_id: uuid.UUID | None = None
    lock_expires_at: datetime | None = None
    is_locked: bool = False
    claimant_flagged: bool = False
    extra_data: dict[str, Any] = Field(default_factory=dict)


class ModeratorQueueResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ModeratorQueueItem]
    total: int


class ClaimFormResponse(BaseModel):
    """What a claimant needs to file a claim (D-20): the public summary plus the finder's
    verification questions. Never the private details, exact location or reporter."""

    model_config = ConfigDict(extra="forbid")

    found_id: uuid.UUID
    title: str
    category: str
    building: str | None
    verification_prompts: list[str]
