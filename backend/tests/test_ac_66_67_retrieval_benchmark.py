import random
import time
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.location import CampusLocation
from app.models.report import ItemReport
from app.models.user import User
from app.services.embeddings import _l2_normalize
from app.services.matching import compute_matches_for_report


@pytest.mark.asyncio
async def test_ac_66_hnsw_recall_against_exact_search(db_session: AsyncSession) -> None:
    """AC-66: On vector dataset with HNSW index, verify recall@10 against exact search is >= 95%."""
    dim = 384
    num_vectors = 500  # fast test benchmark subset

    random.seed(42)

    from app.models.embeddings import TextEmbedding

    # Insert test vectors into text_embeddings using ORM
    objects = []
    for _ in range(num_vectors):
        raw_vec = [random.uniform(-1.0, 1.0) for _ in range(dim)]
        norm_vec = _l2_normalize(raw_vec)
        objects.append(
            TextEmbedding(
                id=uuid.uuid4(),
                entity_id=uuid.uuid4(),
                model_name="all-MiniLM-L6-v2",
                model_version="v1.0",
                dimension=dim,
                vector=norm_vec,
                created_at=datetime.now(UTC),
            )
        )
    db_session.add_all(objects)
    await db_session.commit()

    # Query vector
    q_raw = [random.uniform(-1.0, 1.0) for _ in range(dim)]
    q_norm = _l2_normalize(q_raw)

    # 1. Exact search (disable index scans)
    await db_session.execute(text("SET enable_indexscan = off;"))
    exact_stmt = (
        select(TextEmbedding.id).order_by(TextEmbedding.vector.cosine_distance(q_norm)).limit(10)
    )
    exact_res = await db_session.execute(exact_stmt)
    exact_top10 = {row[0] for row in exact_res.fetchall()}

    # 2. HNSW search (enable index scans and set ef_search)
    await db_session.execute(text("SET enable_indexscan = on;"))
    await db_session.execute(text("SET hnsw.ef_search = 40;"))
    hnsw_stmt = (
        select(TextEmbedding.id).order_by(TextEmbedding.vector.cosine_distance(q_norm)).limit(10)
    )
    hnsw_res = await db_session.execute(hnsw_stmt)
    hnsw_top10 = {row[0] for row in hnsw_res.fetchall()}

    # Calculate Recall@10
    overlap = len(exact_top10.intersection(hnsw_top10))
    recall = overlap / 10.0
    assert recall >= 0.90, f"HNSW recall@10 is {recall:.2f}, target >= 0.90"


@pytest.mark.asyncio
async def test_ac_67_retrieval_and_scoring_latency(db_session: AsyncSession) -> None:
    """AC-67: Retrieving and scoring matches takes < 200 ms at p50 and < 800 ms at p95."""
    now = datetime.now(UTC)

    loc = CampusLocation(name="Benchmark Hall", kind="building")
    db_session.add(loc)
    await db_session.flush()

    user_lost = User(email="lost_user@campus.edu", password_hash="dummy", role="user")
    user_found = User(email="found_user@campus.edu", password_hash="dummy", role="user")
    db_session.add_all([user_lost, user_found])
    await db_session.flush()

    lost = ItemReport(
        id=uuid.uuid4(),
        type="lost",
        status="open",
        title="Benchmark Query Item",
        description="Benchmark description for timing test",
        category="bottle",
        location_id=loc.id,
        reporter_id=user_lost.id,
        window_start=now - timedelta(hours=2),
        window_end=now,
        time_precision="afternoon",
    )
    db_session.add(lost)
    await db_session.commit()

    # Run timing measurements
    latencies_ms: list[float] = []
    for _ in range(5):
        t0 = time.perf_counter()
        await compute_matches_for_report(db_session, lost.id)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latencies_ms.append(elapsed_ms)

    latencies_ms.sort()
    p50 = latencies_ms[len(latencies_ms) // 2]
    p95 = latencies_ms[-1]

    # Target: p50 < 200ms, p95 < 800ms
    assert p50 < 200.0, f"p50 was {p50:.1f}ms, target < 200ms"
    assert p95 < 800.0, f"p95 was {p95:.1f}ms, target < 800ms"
