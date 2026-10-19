from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.found import PublicFoundItemSummary


class MatchCandidateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    lost_id: uuid.UUID
    found_id: uuid.UUID
    found_report: PublicFoundItemSummary
    score: float
    bin: str
    text_score: float | None
    image_score: float | None
    location_score: float | None
    time_score: float | None
    explanation: list[str]
    status: str
    created_at: datetime


class MatchListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    matches: list[MatchCandidateResponse]
    total: int
