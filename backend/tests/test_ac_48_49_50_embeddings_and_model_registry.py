from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.embeddings import ModelRegistry, TextEmbedding
from app.models.jobs import BackgroundJob
from app.models.location import CampusLocation
from app.models.report import ItemReport
from app.models.user import User
from app.services.embeddings import (
    activate_model_version,
    upsert_report_text_embedding,
)


@pytest.fixture
async def sample_report(db_session: AsyncSession) -> ItemReport:
    user = User(
        email="embed_test@campus.edu",
        password_hash="any_hash",
        role="user",
        email_verified_at=datetime.now(UTC),
    )
    loc = CampusLocation(name="Library", kind="building")
    db_session.add_all([user, loc])
    await db_session.flush()

    report = ItemReport(
        type="lost",
        status="open",
        title="Black Leather Wallet",
        description="Bi-fold wallet with campus ID card.",
        category="wallet",
        location_id=loc.id,
        reporter_id=user.id,
        window_start=datetime.now(UTC),
        window_end=datetime.now(UTC),
        time_precision="exact",
    )
    db_session.add(report)
    await db_session.commit()
    return report


@pytest.mark.asyncio
async def test_ac_48_idempotent_embedding_storage(
    db_session: AsyncSession, sample_report: ItemReport
) -> None:
    """AC-48: Running the embedding job again for the same entity and model version leaves exactly one embedding row."""
    # First execution
    await upsert_report_text_embedding(
        db=db_session,
        report=sample_report,
        model_name="all-MiniLM-L6-v2",
        model_version="v1.0",
    )
    await db_session.commit()

    # Second execution (re-run)
    await upsert_report_text_embedding(
        db=db_session,
        report=sample_report,
        model_name="all-MiniLM-L6-v2",
        model_version="v1.0",
    )
    await db_session.commit()

    stmt = (
        select(func.count())
        .select_from(TextEmbedding)
        .where(
            TextEmbedding.entity_id == sample_report.id,
            TextEmbedding.model_version == "v1.0",
        )
    )
    count = (await db_session.execute(stmt)).scalar_one()
    assert count == 1


@pytest.mark.asyncio
async def test_ac_49_model_registry_and_backfill_trigger(
    db_session: AsyncSession, sample_report: ItemReport
) -> None:
    """AC-49: Embeddings record metadata; activating new version triggers backfill jobs."""
    # Seed active model v1.0
    reg = ModelRegistry(
        model_type="text",
        model_name="all-MiniLM-L6-v2",
        model_version="v1.0",
        dimension=384,
        is_active=True,
    )
    db_session.add(reg)
    await db_session.commit()

    # Generate v1.0 embedding
    emb = await upsert_report_text_embedding(
        db=db_session,
        report=sample_report,
        model_name="all-MiniLM-L6-v2",
        model_version="v1.0",
    )
    await db_session.commit()

    assert emb.model_name == "all-MiniLM-L6-v2"
    assert emb.model_version == "v1.0"
    assert emb.dimension == 384
    assert len(emb.vector) == 384

    # Activate version v2.0 -> triggers backfill
    new_reg = await activate_model_version(
        db=db_session,
        model_type="text",
        model_name="all-MiniLM-L6-v2",
        model_version="v2.0",
        dimension=384,
    )
    await db_session.commit()

    assert new_reg.is_active is True

    # Check backfill job enqueued for open report
    stmt = select(BackgroundJob).where(
        BackgroundJob.entity_id == sample_report.id,
        BackgroundJob.kind == "embed_report_text",
        BackgroundJob.payload["model_version"].astext == "v2.0",
    )
    job = (await db_session.execute(stmt)).scalar_one_or_none()
    assert job is not None


@pytest.mark.asyncio
async def test_ac_50_database_rejects_wrong_vector_dimension(
    db_session: AsyncSession, sample_report: ItemReport
) -> None:
    """AC-50: The database rejects a vector of the wrong dimension."""
    # Attempt inserting a 128-dimensional vector into a 384-dimensional pgvector column
    wrong_dim_vector = [0.1] * 128
    invalid_emb = TextEmbedding(
        entity_id=sample_report.id,
        model_name="all-MiniLM-L6-v2",
        model_version="v1.0",
        dimension=128,  # mismatch with column definition Vector(384)
        vector=wrong_dim_vector,
    )
    db_session.add(invalid_emb)

    with pytest.raises(DBAPIError):
        await db_session.commit()
    await db_session.rollback()
