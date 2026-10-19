from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from app.core.database import get_db
from app.main import app


@pytest.mark.asyncio
async def test_ac_138_walking_skeleton_health(async_client: AsyncClient) -> None:
    """AC-138 (skeleton): Verify walking skeleton /api/health endpoint and contract."""
    mock_db = AsyncMock()
    mock_db.execute.return_value = None

    async def override_get_db() -> AsyncGenerator[AsyncMock, None]:
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
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
    finally:
        app.dependency_overrides.clear()


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
