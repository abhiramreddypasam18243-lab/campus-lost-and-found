"""SQLAlchemy models for claims and moderation (spec sections 5.3, 15: AC-75 to AC-85)."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Claim(Base):
    """Claim on a found item with evidence, verification prompt answers,

    and moderation lifecycle states.
    """

    __tablename__ = "claims"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    found_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("item_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lost_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("item_reports.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    claimant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    answers: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    image_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default="[]")

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="submitted", index=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    locked_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    lock_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    # Relationships
    found_report = relationship("ItemReport", foreign_keys=[found_id])
    lost_report = relationship("ItemReport", foreign_keys=[lost_id])
    claimant = relationship("User", foreign_keys=[claimant_id])
    reviewer = relationship("User", foreign_keys=[reviewer_id])
    locked_by = relationship("User", foreign_keys=[locked_by_id])

    __table_args__ = (
        Index("ix_claims_claimant_status", "claimant_id", "status"),
        Index("ix_claims_found_status", "found_id", "status"),
        Index("ix_claims_status_submitted_at", "status", "submitted_at"),
    )
