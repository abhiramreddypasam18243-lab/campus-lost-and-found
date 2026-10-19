import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.jobs import BackgroundJob
from app.services.job_queue import claim_jobs


@pytest.mark.asyncio
async def test_ac_46_concurrent_workers_skip_locked(
    db_session: AsyncSession,
) -> None:
    """AC-46: With 2 workers and concurrent claims, every job completes exactly once using FOR UPDATE SKIP LOCKED."""
    # Seed 200 jobs for reliable and fast concurrency testing
    total_jobs = 200
    now = datetime.now(UTC)
    jobs = [
        BackgroundJob(
            kind="test_job",
            entity_id=uuid.uuid4(),
            status="pending",
            run_after=now,
        )
        for _ in range(total_jobs)
    ]
    db_session.add_all(jobs)
    await db_session.commit()

    # Shared counter for executions
    processed_ids: list[uuid.UUID] = []
    lock = asyncio.Lock()

    # Bind factory for independent sessions per worker
    session_maker = async_sessionmaker(
        bind=db_session.bind,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def worker_loop(worker_name: str) -> int:
        local_count = 0
        while True:
            async with session_maker() as session:
                async with session.begin():
                    claimed = await claim_jobs(session, batch_size=20, locked_by=worker_name)
                    if not claimed:
                        break
                    for job in claimed:
                        job.status = "completed"
                        async with lock:
                            processed_ids.append(job.id)
                        local_count += 1
                await session.commit()
            await asyncio.sleep(0.005)
        return local_count

    # Run 2 workers concurrently
    w1_count, w2_count = await asyncio.gather(
        worker_loop("worker_1"),
        worker_loop("worker_2"),
    )

    # 1. Total processed equals total seeded
    assert len(processed_ids) == total_jobs
    assert w1_count + w2_count == total_jobs

    # 2. Both workers processed jobs (concurrency confirmed)
    assert w1_count > 0
    assert w2_count > 0

    # 3. Every job processed exactly once (no duplicates)
    assert len(set(processed_ids)) == total_jobs

    # 4. Check DB state
    stmt = (
        select(func.count()).select_from(BackgroundJob).where(BackgroundJob.status == "completed")
    )
    completed_in_db = (await db_session.execute(stmt)).scalar_one()
    assert completed_in_db == total_jobs
