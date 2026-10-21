"""Worker job execution: embeddings, then matching (spec 6.1, 6.5; AC-45 to AC-49, AC-63).

Each job runs in its own transaction. Embedding a report or photo re-scores that report
against its open counterparts, so a new report triggers matching in both directions.
Jobs are idempotent: re-running one upserts the same embedding rows and candidates.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.models.jobs import BackgroundJob
from app.models.report import ItemImage, ItemReport
from app.services.embedder import Embedder
from app.services.embeddings import (
    CLIP_TEXT_MODEL_SUFFIX,
    report_embedding_text,
    upsert_image_space_embedding,
    upsert_report_text_embedding,
)
from app.services.job_queue import claim_jobs, handle_job_failure
from app.services.matching import compute_matches_for_report

logger = logging.getLogger("worker")


async def _embed_report_text(db: AsyncSession, job: BackgroundJob, embedder: Embedder) -> None:
    settings = get_settings()
    report = (
        await db.execute(select(ItemReport).where(ItemReport.id == job.entity_id))
    ).scalar_one_or_none()
    if report is None:
        return  # deleted since enqueue; nothing to do

    text_model = job.payload.get("model_name", settings.TEXT_MODEL_NAME)
    text_version = job.payload.get("model_version", settings.TEXT_MODEL_VERSION)
    content = report_embedding_text(report)
    await upsert_report_text_embedding(
        db,
        report,
        model_name=text_model,
        model_version=text_version,
        vector=embedder.embed_text(content),
    )
    # CLIP text vector of the same public text, for the text-to-image signal (spec 6.2).
    await upsert_image_space_embedding(
        db,
        entity_id=report.id,
        model_name=settings.CLIP_MODEL_NAME + CLIP_TEXT_MODEL_SUFFIX,
        model_version=settings.CLIP_MODEL_VERSION,
        vector=embedder.embed_clip_text(content),
    )
    await db.flush()
    await compute_matches_for_report(db, report.id)


async def _embed_report_image(db: AsyncSession, job: BackgroundJob, embedder: Embedder) -> None:
    settings = get_settings()
    image = (
        await db.execute(select(ItemImage).where(ItemImage.id == job.entity_id))
    ).scalar_one_or_none()
    if image is None or image.deleted_at is not None:
        return

    path = Path(settings.UPLOAD_DIR) / image.storage_key
    await upsert_image_space_embedding(
        db,
        entity_id=image.id,
        model_name=job.payload.get("model_name", settings.CLIP_MODEL_NAME),
        model_version=job.payload.get("model_version", settings.CLIP_MODEL_VERSION),
        vector=embedder.embed_image(path),
    )
    await db.flush()
    await compute_matches_for_report(db, image.report_id)


HANDLERS = {
    "embed_report_text": _embed_report_text,
    "embed_report_image": _embed_report_image,
}


async def run_job(db: AsyncSession, job: BackgroundJob, embedder: Embedder) -> None:
    handler = HANDLERS.get(job.kind)
    if handler is None:
        raise ValueError(f"unknown job kind: {job.kind}")
    await handler(db, job, embedder)


async def process_available_jobs(
    session_factory: async_sessionmaker[AsyncSession],
    embedder: Embedder,
    worker_id: str,
    batch_size: int = 20,
) -> int:
    """Claim a batch (FOR UPDATE SKIP LOCKED), then run each job in its own transaction.

    Returns the number of jobs claimed. A failing job is rolled back and rescheduled with
    backoff (AC-47); its error message is stored, never report text or private data.
    """
    async with session_factory() as db:
        jobs = await claim_jobs(db, batch_size=batch_size, locked_by=worker_id)
        job_ids = [j.id for j in jobs]
        await db.commit()

    for job_id in job_ids:
        async with session_factory() as db:
            job = await db.get(BackgroundJob, job_id)
            if job is None:
                continue
            kind = job.kind  # read before a rollback expires the instance
            try:
                await run_job(db, job, embedder)
                job.status = "completed"
                job.locked_at = None
                job.locked_by = None
                await db.commit()
            except Exception as exc:
                await db.rollback()
                failed = await db.get(BackgroundJob, job_id)
                if failed is not None:
                    handle_job_failure(failed, type(exc).__name__)
                    await db.commit()
                logger.warning("job %s (%s) failed: %s", job_id, kind, type(exc).__name__)
    return len(job_ids)
