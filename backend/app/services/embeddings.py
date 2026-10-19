import hashlib
import math
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.embeddings import ModelRegistry, TextEmbedding
from app.models.jobs import BackgroundJob
from app.models.report import ItemReport


def utc_now() -> datetime:
    return datetime.now(UTC)


def _l2_normalize(vector: list[float]) -> list[float]:
    """Normalize a vector so its Euclidean norm equals 1.0."""
    norm = math.sqrt(sum(x * x for x in vector))
    if norm < 1e-12:
        return [0.0] * len(vector)
    return [x / norm for x in vector]


def generate_standin_text_embedding(text: str, dimension: int = 384) -> list[float]:
    """Generate a deterministic, L2-normalized stand-in embedding vector for fast test execution (Project Rule 11)."""
    raw_hash = hashlib.sha256(text.encode("utf-8")).digest()
    values: list[float] = []
    # Expand or sample hash bytes into floats in [-1.0, 1.0]
    for i in range(dimension):
        byte_val = raw_hash[(i * 7) % len(raw_hash)]
        # Normalize byte (0-255) to range [-1.0, 1.0]
        values.append((byte_val / 127.5) - 1.0)
    return _l2_normalize(values)


def generate_standin_image_embedding(seed: str, dimension: int = 512) -> list[float]:
    """Generate a deterministic, L2-normalized stand-in image embedding vector."""
    raw_hash = hashlib.sha512(seed.encode("utf-8")).digest()
    values: list[float] = []
    for i in range(dimension):
        byte_val = raw_hash[(i * 11) % len(raw_hash)]
        values.append((byte_val / 127.5) - 1.0)
    return _l2_normalize(values)


async def upsert_report_text_embedding(
    db: AsyncSession,
    report: ItemReport,
    model_name: str = "all-MiniLM-L6-v2",
    model_version: str = "v1.0",
) -> TextEmbedding:
    """Idempotently compute and store a text embedding for a report (AC-48, AC-49)."""
    content = f"{report.category} {report.title} {report.description}"
    vector = generate_standin_text_embedding(content, dimension=384)

    stmt = select(TextEmbedding).where(
        TextEmbedding.entity_id == report.id,
        TextEmbedding.model_name == model_name,
        TextEmbedding.model_version == model_version,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing is not None:
        existing.vector = vector
        return existing

    emb = TextEmbedding(
        entity_id=report.id,
        model_name=model_name,
        model_version=model_version,
        dimension=384,
        vector=vector,
    )
    db.add(emb)
    return emb


async def activate_model_version(
    db: AsyncSession,
    model_type: str,
    model_name: str,
    model_version: str,
    dimension: int = 384,
) -> ModelRegistry:
    """Activate a model version in the registry and enqueue backfill jobs (AC-49)."""
    # Deactivate current active models for this type
    deactivate_stmt = select(ModelRegistry).where(
        ModelRegistry.model_type == model_type,
        ModelRegistry.is_active.is_(True),
    )
    active_models = (await db.execute(deactivate_stmt)).scalars().all()
    for m in active_models:
        m.is_active = False

    # Get or create target model registry entry
    stmt = select(ModelRegistry).where(
        ModelRegistry.model_name == model_name,
        ModelRegistry.model_version == model_version,
    )
    target = (await db.execute(stmt)).scalar_one_or_none()
    if target is None:
        target = ModelRegistry(
            model_type=model_type,
            model_name=model_name,
            model_version=model_version,
            dimension=dimension,
            is_active=True,
        )
        db.add(target)
    else:
        target.is_active = True

    # AC-49: Trigger backfill jobs for all open reports
    reports_stmt = select(ItemReport).where(ItemReport.status == "open")
    open_reports = (await db.execute(reports_stmt)).scalars().all()

    for r in open_reports:
        backfill_job = BackgroundJob(
            kind="embed_report_text" if model_type == "text" else "embed_report_image",
            entity_id=r.id,
            payload={"model_name": model_name, "model_version": model_version},
            status="pending",
            attempts=0,
            run_after=utc_now(),
        )
        db.add(backfill_job)

    return target
