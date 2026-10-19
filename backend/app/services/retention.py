"""Retention service for data expiration, photo/evidence purging, and audit log maintenance (AC-100, AC-101, AC-102)."""

import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.audit import AuditLog
from app.models.claims import Claim
from app.models.embeddings import ImageEmbedding
from app.models.report import ItemImage, ItemReport
from app.models.user import User
from app.services.audit import write_audit_log


def get_utcnow() -> datetime:
    return datetime.now(UTC)


async def expire_unclaimed_reports(
    db: AsyncSession,
    retention_days: int = 90,
    current_time: datetime | None = None,
) -> int:
    """AC-100: A found report still 'open' after 90 days becomes 'unclaimed_expired'."""
    now = current_time or get_utcnow()
    cutoff = now - timedelta(days=retention_days)

    stmt = select(ItemReport).where(
        ItemReport.type == "found",
        ItemReport.status == "open",
        ItemReport.created_at <= cutoff,
    )
    result = await db.execute(stmt)
    stale_reports = list(result.scalars().all())

    count = 0
    for report in stale_reports:
        report.status = "unclaimed_expired"
        report.updated_at = now
        await write_audit_log(
            db=db,
            actor_id=None,
            role="system",
            action="retention.expired",
            entity_type="item_report",
            entity_id=report.id,
            summary={"days_unclaimed": retention_days},
        )
        count += 1

    if count > 0:
        await db.commit()
    return count


async def record_report_disposition(
    db: AsyncSession,
    report_id: uuid.UUID,
    disposition: str,
    moderator: User,
    current_time: datetime | None = None,
) -> ItemReport:
    """AC-100: Moderator records disposition ('donated', 'disposed', 'kept') on unclaimed_expired report."""
    now = current_time or get_utcnow()

    if moderator.role not in ("moderator", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="forbidden",
        )

    valid_dispositions = ("donated", "disposed", "kept")
    if disposition not in valid_dispositions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid_disposition",
        )

    report = await db.get(ItemReport, report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="report_not_found",
        )

    if report.status != "unclaimed_expired":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="report_not_unclaimed_expired",
        )

    report.disposition = disposition
    report.reviewed_by = moderator.id
    report.updated_at = now

    await write_audit_log(
        db=db,
        actor_id=moderator.id,
        role=moderator.role,
        action="report.disposition_recorded",
        entity_type="item_report",
        entity_id=report.id,
        summary={"disposition": disposition},
    )
    await db.commit()
    await db.refresh(report)
    return report


async def purge_closed_images(
    db: AsyncSession,
    purge_days: int = 30,
    current_time: datetime | None = None,
) -> int:
    """AC-101: Images are deleted 30 days after their report closes and claim evidence 30 days after claim closes.

    Files are removed from storage, rows are marked deleted, and embeddings are removed.
    """
    now = current_time or get_utcnow()
    cutoff = now - timedelta(days=purge_days)
    upload_dir = Path(get_settings().UPLOAD_DIR)

    # 1. Reports closed > 30 days
    report_stmt = (
        select(ItemImage)
        .join(ItemReport, ItemImage.report_id == ItemReport.id)
        .where(
            ItemReport.status.in_(["closed", "returned", "removed", "unclaimed_expired"]),
            ItemReport.updated_at <= cutoff,
            ItemImage.deleted_at.is_(None),
        )
    )
    report_images = list((await db.execute(report_stmt)).scalars().all())

    purged_count = 0
    for img in report_images:
        main_file = upload_dir / img.storage_key
        thumb_file = upload_dir / f"thumb_{img.storage_key}"
        if main_file.exists():
            try:
                os.remove(main_file)
            except OSError:
                pass
        if thumb_file.exists():
            try:
                os.remove(thumb_file)
            except OSError:
                pass

        img.deleted_at = now

        # Delete embeddings
        await db.execute(delete(ImageEmbedding).where(ImageEmbedding.entity_id == img.id))

        await write_audit_log(
            db=db,
            actor_id=None,
            role="system",
            action="retention.purged",
            entity_type="item_image",
            entity_id=img.id,
            summary={"report_id": str(img.report_id)},
        )
        purged_count += 1

    # 2. Claims closed > 30 days: clear private evidence photos
    claim_stmt = select(Claim).where(
        Claim.status.in_(["completed", "rejected", "withdrawn", "expired"]),
        Claim.updated_at <= cutoff,
    )
    closed_claims = list((await db.execute(claim_stmt)).scalars().all())
    for claim in closed_claims:
        if claim.image_ids:
            claim.image_ids = []
            claim.updated_at = now
            purged_count += 1

    if purged_count > 0:
        await db.commit()
    return purged_count


async def purge_old_audit_logs(
    db: AsyncSession,
    retention_days: int = 365,
    current_time: datetime | None = None,
) -> int:
    """AC-102: Audit rows older than configured period can be removed ONLY by retention job's privileged role."""
    now = current_time or get_utcnow()
    cutoff = now - timedelta(days=retention_days)

    # Set session variable for privileged retention bypass of append-only trigger
    await db.execute(text("SET LOCAL app.allow_retention_purge = 'true';"))

    stmt = delete(AuditLog).where(AuditLog.created_at <= cutoff)
    result = await db.execute(stmt)
    await db.commit()
    return int(getattr(result, "rowcount", 0))
