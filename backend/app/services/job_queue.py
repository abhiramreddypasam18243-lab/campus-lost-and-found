import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.jobs import BackgroundJob

BACKOFF_MINUTES = [1, 2, 4, 8]


def utc_now() -> datetime:
    return datetime.now(UTC)


async def enqueue_job(
    db: AsyncSession,
    kind: str,
    entity_id: uuid.UUID,
    payload: dict[str, Any] | None = None,
    run_after: datetime | None = None,
) -> BackgroundJob:
    """Enqueue a job in the same database transaction as business logic (outbox pattern)."""
    job = BackgroundJob(
        kind=kind,
        entity_id=entity_id,
        payload=payload or {},
        status="pending",
        attempts=0,
        max_attempts=5,
        run_after=run_after or utc_now(),
    )
    db.add(job)
    return job


async def claim_jobs(
    db: AsyncSession, batch_size: int = 20, locked_by: str = "worker"
) -> list[BackgroundJob]:
    """Claim pending jobs atomically using SELECT FOR UPDATE SKIP LOCKED (AC-46)."""
    now = utc_now()
    stmt = (
        select(BackgroundJob)
        .where(
            BackgroundJob.status == "pending",
            BackgroundJob.run_after <= now,
        )
        .order_by(BackgroundJob.run_after.asc(), BackgroundJob.id.asc())
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )
    result = await db.execute(stmt)
    jobs = list(result.scalars().all())

    for job in jobs:
        job.status = "running"
        job.locked_at = now
        job.locked_by = locked_by

    return jobs


def handle_job_failure(
    job: BackgroundJob, error_msg: str, current_time: datetime | None = None
) -> None:
    """Apply exponential backoff (1, 2, 4, 8 min) or fail after 5 attempts (AC-47)."""
    now = current_time or utc_now()
    job.attempts += 1
    job.last_error = error_msg
    job.locked_at = None
    job.locked_by = None

    if job.attempts < 5:
        job.status = "pending"
        backoff_idx = min(job.attempts - 1, len(BACKOFF_MINUTES) - 1)
        job.run_after = now + timedelta(minutes=BACKOFF_MINUTES[backoff_idx])
    else:
        job.status = "failed"
