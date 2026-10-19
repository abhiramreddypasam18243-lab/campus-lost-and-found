"""Analytics service layer for dashboard metrics (AC-105 to AC-108)."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.analytics import (
    SYNTHETIC_DATA_BANNER,
    calculate_median_duration,
    calculate_recovery_rate,
    calculate_unclaimed_rate,
)
from app.models.claims import Claim
from app.models.handover import Handover
from app.models.report import ItemReport
from app.schemas.analytics import DashboardMetricsResponse


def _to_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def get_utcnow() -> datetime:
    return datetime.now(UTC)


async def get_dashboard_analytics(
    db: AsyncSession, current_time: datetime | None = None
) -> DashboardMetricsResponse:
    """AC-105, AC-107, AC-108: Compute aggregated operational metrics for found reports and recovery times."""
    now = _to_utc(current_time) or get_utcnow()

    # Query all found reports
    stmt = select(ItemReport).where(ItemReport.type == "found")
    reports = list((await db.execute(stmt)).scalars().all())

    total_created = len(reports)
    open_reports = [r for r in reports if r.status == "open"]
    returned_reports = [r for r in reports if r.status == "returned"]
    unclaimed_expired_reports = [r for r in reports if r.status == "unclaimed_expired"]

    open_count = len(open_reports)
    returned_count = len(returned_reports)
    unclaimed_expired_count = len(unclaimed_expired_reports)

    # Recovery durations in hours
    recovery_durations: list[float] = []
    if returned_reports:
        # Join with completed handovers if available, otherwise use report updated_at
        returned_ids = [r.id for r in returned_reports]
        handover_stmt = (
            select(Claim.found_id, Handover.verified_at)
            .join(Handover, Claim.id == Handover.claim_id)
            .where(Claim.found_id.in_(returned_ids), Handover.status == "verified")
        )
        handover_rows = (await db.execute(handover_stmt)).all()
        handover_map = {found_id: verified_at for found_id, verified_at in handover_rows}

        for r in returned_reports:
            completion_time = handover_map.get(r.id) or r.updated_at
            c_time = _to_utc(completion_time)
            c_created = _to_utc(r.created_at)
            if c_time and c_created:
                diff_hours = (c_time - c_created).total_seconds() / 3600.0
                if diff_hours >= 0:
                    recovery_durations.append(diff_hours)

    median_time_to_recovery = calculate_median_duration(recovery_durations)

    # Queue age for open reports in hours
    queue_ages: list[float] = []
    for r in open_reports:
        c_created = _to_utc(r.created_at)
        if c_created:
            age_hours = (now - c_created).total_seconds() / 3600.0
            if age_hours >= 0:
                queue_ages.append(age_hours)
    median_queue_age = calculate_median_duration(queue_ages)

    recovery_rate = calculate_recovery_rate(returned_count, unclaimed_expired_count)
    unclaimed_rate = calculate_unclaimed_rate(unclaimed_expired_count, total_created)

    return DashboardMetricsResponse(
        total_created=total_created,
        open_count=open_count,
        returned_count=returned_count,
        unclaimed_expired_count=unclaimed_expired_count,
        recovery_rate=recovery_rate,
        unclaimed_rate=unclaimed_rate,
        median_time_to_recovery_hours=round(median_time_to_recovery, 2)
        if median_time_to_recovery is not None
        else None,
        queue_age_median_hours=round(median_queue_age, 2)
        if median_queue_age is not None
        else None,
        banner_notice=SYNTHETIC_DATA_BANNER,
        is_synthetic_demo=True,
    )
