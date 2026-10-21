import asyncio
import logging
import os
import signal
import socket
import sys
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.dialects.postgresql import insert

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.jobs import WorkerHeartbeat
from app.services.embedder import get_embedder
from app.services.handover import expire_stale_handovers
from app.services.job_runner import process_available_jobs
from app.services.retention import expire_unclaimed_reports, purge_closed_images

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [worker] %(message)s",
)
logger = logging.getLogger("worker")

running = True


def handle_stop(sig: int, frame: Any) -> None:
    global running
    logger.info(f"Received signal {sig}, shutting down worker cleanly...")
    running = False


async def write_heartbeat(worker_id: str) -> None:
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        stmt = insert(WorkerHeartbeat).values(worker_id=worker_id, last_seen_at=now)
        stmt = stmt.on_conflict_do_update(
            index_elements=[WorkerHeartbeat.worker_id], set_={"last_seen_at": now}
        )
        await db.execute(stmt)
        await db.commit()


async def run_maintenance() -> None:
    """Retention (spec 5.5) and handover expiry (spec 5.4); each step commits on its own."""
    settings = get_settings()
    async with AsyncSessionLocal() as db:
        expired_codes = await expire_stale_handovers(db)
        expired_reports = await expire_unclaimed_reports(
            db, retention_days=settings.RETENTION_UNCLAIMED_FOUND_DAYS
        )
        purged_images = await purge_closed_images(
            db, purge_days=settings.RETENTION_CLOSED_IMAGE_DAYS
        )
    logger.info(
        "maintenance: %d handovers expired, %d reports expired, %d images purged",
        expired_codes,
        expired_reports,
        purged_images,
    )


async def run_worker_loop() -> None:
    settings = get_settings()
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    logger.info("Loading embedding backend '%s'...", settings.EMBEDDING_BACKEND)
    embedder = get_embedder()  # fail fast at startup if baked model weights are missing
    logger.info("Worker %s started.", worker_id)

    last_maintenance = 0.0
    while running:
        try:
            await write_heartbeat(worker_id)
            if time.monotonic() - last_maintenance >= settings.WORKER_MAINTENANCE_INTERVAL_SECONDS:
                await run_maintenance()
                last_maintenance = time.monotonic()
            claimed = await process_available_jobs(AsyncSessionLocal, embedder, worker_id)
        except Exception as exc:  # keep the loop alive; the error type is enough to debug
            logger.error("worker iteration failed: %s", type(exc).__name__)
            claimed = 0
        if claimed == 0:
            await asyncio.sleep(settings.WORKER_POLL_SECONDS)
    logger.info("Worker stopped.")


def main() -> None:
    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)
    try:
        asyncio.run(run_worker_loop())
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)


if __name__ == "__main__":
    main()
