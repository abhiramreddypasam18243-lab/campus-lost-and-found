"""The worker pipeline: queued embedding jobs are run, then matching (AC-45, AC-47, AC-55, AC-63).

Uses the stand-in embedder, so no model weights are needed.
"""

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.embeddings import ImageEmbedding, TextEmbedding
from app.models.jobs import BackgroundJob
from app.models.location import CampusLocation
from app.models.matching import MatchCandidate
from app.models.notifications import Notification
from app.models.report import ItemImage, ItemReport
from app.models.user import User
from app.services.embedder import StandinEmbedder
from app.services.job_queue import enqueue_job
from app.services.job_runner import process_available_jobs
from app.services.matching import compute_matches_for_report

settings = get_settings()

# The runner opens its own sessions per job, as the worker does.
TestAsyncSessionLocal = async_sessionmaker(
    bind=create_async_engine(settings.DATABASE_URL, poolclass=NullPool),
    class_=AsyncSession,
    expire_on_commit=False,
)


def _user(email: str) -> User:
    return User(
        email=email,
        password_hash=hash_password("Pass1234!"),
        role="user",
        email_verified_at=datetime.now(UTC),
    )


def _report(kind: str, reporter: User, loc: CampusLocation, **kw: Any) -> ItemReport:
    now = datetime.now(UTC)
    fields: dict[str, Any] = {
        "title": "Blue steel water bottle",
        "description": "Dark blue insulated bottle with a dented base",
        "category": "bottle",
        "window_start": now - timedelta(hours=2),
        "window_end": now - timedelta(hours=1),
    }
    fields.update(kw)
    return ItemReport(
        id=uuid.uuid4(),
        type=kind,
        status="open",
        location_id=loc.id,
        reporter_id=reporter.id,
        time_precision="exact",
        **fields,
    )


@pytest.fixture
async def scenario(db_session: AsyncSession) -> dict[str, Any]:
    loc = CampusLocation(name="Library", kind="building")
    db_session.add(loc)
    owner, finder = _user("owner@campus.edu"), _user("finder@campus.edu")
    db_session.add_all([owner, finder])
    await db_session.flush()
    lost = _report("lost", owner, loc, title="Lost navy flask")
    found = _report("found", finder, loc)
    db_session.add_all([lost, found])
    await db_session.commit()
    return {"loc": loc, "owner": owner, "finder": finder, "lost": lost, "found": found}


@pytest.mark.asyncio
async def test_ac_45_63_worker_embeds_then_matches(
    db_session: AsyncSession, scenario: dict[str, Any]
) -> None:
    """Queued text jobs produce text + CLIP-text embeddings and a scored candidate."""
    lost, found = scenario["lost"], scenario["found"]
    lost_id, found_id = lost.id, found.id
    await enqueue_job(db_session, kind="embed_report_text", entity_id=lost.id)
    await enqueue_job(db_session, kind="embed_report_text", entity_id=found.id)
    await db_session.commit()

    claimed = await process_available_jobs(TestAsyncSessionLocal, StandinEmbedder(), "test")
    assert claimed == 2

    db_session.expire_all()
    statuses = (await db_session.execute(select(BackgroundJob.status))).scalars().all()
    assert sorted(statuses) == ["completed", "completed"]

    for report_id in (lost_id, found_id):
        text_rows = (
            (
                await db_session.execute(
                    select(TextEmbedding).where(TextEmbedding.entity_id == report_id)
                )
            )
            .scalars()
            .all()
        )
        assert [(r.model_name, r.model_version) for r in text_rows] == [
            (settings.TEXT_MODEL_NAME, settings.TEXT_MODEL_VERSION)
        ]
        clip_rows = (
            (
                await db_session.execute(
                    select(ImageEmbedding).where(ImageEmbedding.entity_id == report_id)
                )
            )
            .scalars()
            .all()
        )
        assert [r.model_name for r in clip_rows] == [settings.CLIP_MODEL_NAME + ":text"]

    cand = (
        await db_session.execute(
            select(MatchCandidate).where(
                MatchCandidate.lost_id == lost_id, MatchCandidate.found_id == found_id
            )
        )
    ).scalar_one()
    assert cand.text_score is not None
    assert cand.image_score is None  # neither report has a photo

    # Idempotent (AC-48, AC-63): re-running the same job leaves one row per model version.
    await enqueue_job(db_session, kind="embed_report_text", entity_id=lost_id)
    await db_session.commit()
    await process_available_jobs(TestAsyncSessionLocal, StandinEmbedder(), "test")
    count = (
        (await db_session.execute(select(TextEmbedding).where(TextEmbedding.entity_id == lost_id)))
        .scalars()
        .all()
    )
    assert len(count) == 1


@pytest.mark.asyncio
async def test_ac_63_pair_waits_for_both_text_embeddings(
    db_session: AsyncSession, scenario: dict[str, Any]
) -> None:
    """Only one side embedded: no candidate and no notification from location/time alone."""
    lost, found = scenario["lost"], scenario["found"]
    found.title = lost.title  # location 1.0 and time 1.0 would otherwise score high
    await db_session.commit()
    await enqueue_job(db_session, kind="embed_report_text", entity_id=lost.id)
    await db_session.commit()

    await process_available_jobs(TestAsyncSessionLocal, StandinEmbedder(), "test")

    db_session.expire_all()
    assert (await db_session.execute(select(MatchCandidate))).scalars().all() == []
    assert (await db_session.execute(select(Notification))).scalars().all() == []


@pytest.mark.asyncio
async def test_ac_55_text_to_image_signal_uses_clip_vectors(
    db_session: AsyncSession,
    scenario: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exactly one side has a photo: image signal = max(0, cos(CLIP text, CLIP photo))."""
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    lost, found = scenario["lost"], scenario["found"]
    lost_id, found_id = lost.id, found.id

    photo_path = tmp_path / "photo.png"
    Image.new("RGB", (32, 32), (20, 40, 160)).save(photo_path)
    image = ItemImage(
        id=uuid.uuid4(),
        report_id=found.id,
        storage_key="photo.png",
        original_mime="image/png",
        sha256="0" * 64,
        dhash="0" * 16,
        width=32,
        height=32,
        is_public=True,
        moderation_status="approved",
    )
    db_session.add(image)
    await enqueue_job(db_session, kind="embed_report_text", entity_id=lost.id)
    await enqueue_job(db_session, kind="embed_report_text", entity_id=found.id)
    await enqueue_job(db_session, kind="embed_report_image", entity_id=image.id)
    await db_session.commit()

    await process_available_jobs(TestAsyncSessionLocal, StandinEmbedder(), "test")

    embedder = StandinEmbedder()
    text_vec = embedder.embed_clip_text(f"{lost.category} {lost.title} {lost.description}")
    photo_vec = embedder.embed_image(photo_path)
    expected = max(0.0, sum(a * b for a, b in zip(text_vec, photo_vec, strict=True)))

    db_session.expire_all()
    cand = (
        await db_session.execute(
            select(MatchCandidate).where(
                MatchCandidate.lost_id == lost_id, MatchCandidate.found_id == found_id
            )
        )
    ).scalar_one()
    assert cand.image_score == pytest.approx(expected, abs=1e-6)


@pytest.mark.asyncio
async def test_ac_47_failing_job_is_rescheduled_with_backoff(db_session: AsyncSession) -> None:
    """A job that raises is rolled back, retried after 1 minute, and keeps only the error type."""
    db_session.add(
        BackgroundJob(kind="no_such_kind", entity_id=uuid.uuid4(), status="pending", attempts=0)
    )
    await db_session.commit()

    before = datetime.now(UTC)
    await process_available_jobs(TestAsyncSessionLocal, StandinEmbedder(), "test")

    db_session.expire_all()
    job = (await db_session.execute(select(BackgroundJob))).scalar_one()
    assert job.status == "pending"
    assert job.attempts == 1
    assert job.last_error == "ValueError"
    assert job.run_after >= before + timedelta(minutes=1)


@pytest.mark.asyncio
async def test_ac_65_found_trigger_notifies_each_lost_owner(
    db_session: AsyncSession, scenario: dict[str, Any]
) -> None:
    """A new found report matching two lost reports notifies each lost report's own owner."""
    loc, owner, found = scenario["loc"], scenario["owner"], scenario["found"]
    other_owner = _user("other_owner@campus.edu")
    db_session.add(other_owner)
    await db_session.flush()
    # Same public text as the found report, so every signal is 1.0 and both pass 0.65.
    lost_a = scenario["lost"]
    lost_a.title = found.title
    lost_b = _report("lost", other_owner, loc)
    db_session.add(lost_b)
    await db_session.commit()

    for report in (lost_a, lost_b, found):
        await enqueue_job(db_session, kind="embed_report_text", entity_id=report.id)
    await db_session.commit()
    await process_available_jobs(TestAsyncSessionLocal, StandinEmbedder(), "test")
    await compute_matches_for_report(db_session, found.id)
    await db_session.commit()

    rows = (
        await db_session.execute(
            select(Notification.user_id, Notification.event_key).where(
                Notification.event_type == "match_suggested"
            )
        )
    ).all()
    recipients = {key.split(":")[1]: user_id for user_id, key in rows}
    assert recipients[str(lost_a.id)] == owner.id
    assert recipients[str(lost_b.id)] == other_owner.id
