import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.categories import is_valid_category
from app.domain.time import TimePrecision


def _clean_location_text(v: str | None) -> str | None:
    """D-22: trim a typed place; blank counts as not given."""
    if v is None:
        return None
    v = " ".join(v.split())
    return v or None


class ImageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    storage_key: str
    width: int
    height: int
    is_public: bool
    dhash: str
    created_at: datetime


class CreateLostReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=3, max_length=120)
    description: str = Field(..., min_length=10, max_length=2000)
    category: str
    location_id: uuid.UUID | None = None
    location_text: str | None = Field(None, max_length=200)
    date: date
    time_precision: TimePrecision
    exact_time: time | None = None

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if not is_valid_category(v):
            raise ValueError(f"Invalid category: {v}")
        return v

    @field_validator("location_text")
    @classmethod
    def clean_location_text(cls, v: str | None) -> str | None:
        return _clean_location_text(v)


class CreateFoundReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=3, max_length=120)
    description: str = Field(..., min_length=10, max_length=2000)
    category: str
    location_id: uuid.UUID | None = None
    location_text: str | None = Field(None, max_length=200)
    date: date
    time_precision: TimePrecision
    exact_time: time | None = None
    private_details: str | None = Field(None, max_length=1000)
    verification_prompts: list[str] = Field(default_factory=list)

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if not is_valid_category(v):
            raise ValueError(f"Invalid category: {v}")
        return v

    @field_validator("location_text")
    @classmethod
    def clean_location_text(cls, v: str | None) -> str | None:
        return _clean_location_text(v)

    @field_validator("verification_prompts")
    @classmethod
    def validate_prompts(cls, v: list[str]) -> list[str]:
        if len(v) > 3:
            raise ValueError("At most 3 verification prompts are allowed.")
        for p in v:
            if len(p) > 200:
                raise ValueError("Verification prompt cannot exceed 200 characters.")
        return v


class ReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    type: str
    status: str
    title: str
    description: str
    category: str
    location_id: uuid.UUID | None
    location_text: str | None = None
    reporter_id: uuid.UUID
    window_start: datetime
    window_end: datetime
    time_precision: str
    private_details: str | None = None
    verification_prompts: list[str] = Field(default_factory=list)
    images: list[ImageResponse] = Field(default_factory=list)
    created_at: datetime
