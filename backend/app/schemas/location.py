import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

LocationKind = Literal["campus", "building", "floor", "room", "area"]


class LocationBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=100)
    kind: LocationKind
    parent_id: uuid.UUID | None = None
    lat: float | None = None
    lng: float | None = None

    @field_validator("lat", mode="after")
    @classmethod
    def round_lat(cls, v: float | None) -> float | None:
        if v is not None:
            return round(v, 3)
        return v

    @field_validator("lng", mode="after")
    @classmethod
    def round_lng(cls, v: float | None) -> float | None:
        if v is not None:
            return round(v, 3)
        return v


class LocationCreate(LocationBase):
    pass


class LocationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=100)
    kind: LocationKind | None = None
    parent_id: uuid.UUID | None = None
    lat: float | None = None
    lng: float | None = None

    @field_validator("lat", mode="after")
    @classmethod
    def round_lat(cls, v: float | None) -> float | None:
        if v is not None:
            return round(v, 3)
        return v

    @field_validator("lng", mode="after")
    @classmethod
    def round_lng(cls, v: float | None) -> float | None:
        if v is not None:
            return round(v, 3)
        return v


class LocationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    parent_id: uuid.UUID | None
    kind: str
    name: str
    lat: float | None = None
    lng: float | None = None
    created_at: datetime


class AdjacencyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    building_a: uuid.UUID
    building_b: uuid.UUID


class AdjacencyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    building_a: uuid.UUID
    building_b: uuid.UUID
