import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


LOCATION_KINDS = ("campus", "building", "floor", "room", "area")


class CampusLocation(Base):
    __tablename__ = "campus_locations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campus_locations.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    lat: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    lng: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    parent: Mapped["CampusLocation | None"] = relationship(
        "CampusLocation",
        remote_side=[id],
        back_populates="children",
    )
    children: Mapped[list["CampusLocation"]] = relationship(
        "CampusLocation",
        back_populates="parent",
    )

    __table_args__ = (
        CheckConstraint(
            f"kind IN {LOCATION_KINDS}",
            name="ck_campus_locations_kind",
        ),
        # Case-insensitive uniqueness for siblings under the same parent (COALESCE for root campus nodes)
        Index(
            "uq_locations_parent_name_ci",
            func.coalesce(parent_id, "00000000-0000-0000-0000-000000000000"),
            func.lower(name),
            unique=True,
        ),
    )


class LocationAdjacency(Base):
    __tablename__ = "location_adjacency"

    building_a: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campus_locations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    building_b: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campus_locations.id", ondelete="CASCADE"),
        primary_key=True,
    )

    __table_args__ = (
        CheckConstraint("building_a != building_b", name="ck_location_adjacency_distinct"),
    )
