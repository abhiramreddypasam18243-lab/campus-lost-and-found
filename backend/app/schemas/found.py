import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.report import ImageResponse


class PublicFoundItemSummary(BaseModel):
    """AC-39 Whitelisted summary schema for public found items listing."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    title: str
    category: str
    description: str
    date: str
    building: str | None
    building_id: uuid.UUID | None
    thumbnail_url: str | None
    created_at: datetime


class PublicFoundItemListResponse(BaseModel):
    """Listing response with stable cursor pagination."""

    model_config = ConfigDict(extra="forbid")

    items: list[PublicFoundItemSummary]
    next_cursor: str | None


class PublicImageDetail(BaseModel):
    """Whitelisted image representation for public view."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    thumbnail_url: str
    image_url: str


class PublicReportDetailResponse(BaseModel):
    """AC-39 Whitelisted detail schema for normal users viewing an open found item."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    type: str
    status: str
    title: str
    description: str
    category: str
    date: str
    building: str | None
    building_id: uuid.UUID | None
    images: list[PublicImageDetail]
    created_at: datetime


class LocationDetail(BaseModel):
    """Location information for staff/owner full views."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    name: str
    kind: str
    parent_id: uuid.UUID | None = None
    lat: float | None = None
    lng: float | None = None


class ReporterSummary(BaseModel):
    """Reporter identity for staff views."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    email: str
    display_name: str | None = None


class FullStaffReportResponse(BaseModel):
    """AC-42 Full detail report view for staff and owners."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    type: str
    status: str
    title: str
    description: str
    category: str
    location_id: uuid.UUID | None
    location_text: str | None = None
    location: LocationDetail | None = None
    reporter_id: uuid.UUID
    reporter: ReporterSummary | None = None
    window_start: datetime
    window_end: datetime
    time_precision: str
    private_details: str | None = None
    verification_prompts: list[str] = []
    images: list[ImageResponse] = []
    disposition: str | None = None
    closed_at: datetime | None = None
    reviewed_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
