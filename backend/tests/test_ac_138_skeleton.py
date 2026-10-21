from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.main import app
from app.models.jobs import WorkerHeartbeat

settings = get_settings()


@pytest.mark.asyncio
async def test_ac_138_walking_skeleton_health(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC-138 / AC-140: /api/health contract; worker is "ok" with a fresh heartbeat."""
    db_session.add(WorkerHeartbeat(worker_id="test-worker", last_seen_at=datetime.now(UTC)))
    await db_session.commit()

    response = await async_client.get("/api/health")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert data["worker"] == "ok"
    assert "version" in data
    assert "environment" in data

    # Check required security headers
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert "strict-origin-when-cross-origin" in response.headers.get("Referrer-Policy", "")
    assert "default-src 'self'" in response.headers.get("Content-Security-Policy", "")


@pytest.mark.asyncio
async def test_ac_140_health_reports_stale_and_missing_worker(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC-140: worker status is derived from the heartbeat, never assumed."""
    response = await async_client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["worker"] == "unknown"

    stale = settings.WORKER_HEARTBEAT_STALE_SECONDS + 1
    db_session.add(
        WorkerHeartbeat(
            worker_id="test-worker", last_seen_at=datetime.now(UTC) - timedelta(seconds=stale)
        )
    )
    await db_session.commit()

    response = await async_client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["worker"] == "stale"


@pytest.mark.asyncio
async def test_ac_138_walking_skeleton_health_db_failure(async_client: AsyncClient) -> None:
    """AC-138: Verify degraded status code and response when database is unreachable."""
    mock_db = AsyncMock()
    mock_db.execute.side_effect = Exception("Database connection refused")

    async def override_get_db() -> AsyncGenerator[AsyncMock, None]:
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = await async_client.get("/api/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"] == "unhealthy"
    finally:
        app.dependency_overrides.clear()
