from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.report import ItemReport
    from app.models.user import User


def utc_now() -> datetime:
    return datetime.now(UTC)


class MatchCandidate(Base):
    __tablename__ = "match_candidates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lost_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("item_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    found_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("item_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    text_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    image_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    time_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    combined_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    bin: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # high, medium, low
    weights_version: Mapped[str] = mapped_column(String(50), nullable=False, default="v1.0")
    model_versions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    explanation: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="suggested", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    lost_report: Mapped[ItemReport] = relationship("ItemReport", foreign_keys=[lost_id])
    found_report: Mapped[ItemReport] = relationship("ItemReport", foreign_keys=[found_id])

    __table_args__ = (
        UniqueConstraint(
            "lost_id", "found_id", "weights_version", name="uq_match_candidates_pair_weights"
        ),
        Index("ix_match_candidates_lost_status", "lost_id", "status"),
        Index("ix_match_candidates_found_status", "found_id", "status"),
    )


class MatchFeedback(Base):
    __tablename__ = "match_feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("match_candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # dismissed
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )

    candidate: Mapped[MatchCandidate] = relationship("MatchCandidate")
    user: Mapped[User] = relationship("User")
