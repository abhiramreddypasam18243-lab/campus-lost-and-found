from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User


@pytest.fixture
async def rate_limited_users(db_session: AsyncSession, async_client: AsyncClient) -> dict[str, any]:
    user1 = User(
        email="user1_rate@campus.edu",
        password_hash=hash_password("Pass1234!"),
        role="user",
        email_verified_at=datetime.now(UTC),
    )
    user2 = User(
        email="user2_rate@campus.edu",
        password_hash=hash_password("Pass1234!"),
        role="user",
        email_verified_at=datetime.now(UTC),
    )
    db_session.add_all([user1, user2])
    await db_session.commit()

    async def get_cookies(email: str) -> dict[str, str]:
        res = await async_client.post(
            "/api/auth/login",
            json={"email": email, "password": "Pass1234!"},
        )
        return {"session_id": res.cookies.get("session_id", "")}

    return {
        "user1": user1,
        "user2": user2,
        "cookies1": await get_cookies("user1_rate@campus.edu"),
        "cookies2": await get_cookies("user2_rate@campus.edu"),
    }


@pytest.mark.asyncio
async def test_ac_43_browse_rate_limiting(
    async_client: AsyncClient, rate_limited_users: dict[str, any]
) -> None:
    """AC-43: The browse endpoints are rate-limited per user (120 requests per minute)

    and return 429 with Retry-After beyond it.
    """
    cookies1 = rate_limited_users["cookies1"]
    cookies2 = rate_limited_users["cookies2"]

    # 1. User 1 sends 120 requests within a minute -> all 200 OK
    for i in range(120):
        res = await async_client.get("/api/found", cookies=cookies1)
        assert res.status_code == 200, f"Request {i + 1} failed with status {res.status_code}"

    # 2. 121st request for User 1 returns 429 Too Many Requests
    res_exceeded = await async_client.get("/api/found", cookies=cookies1)
    assert res_exceeded.status_code == 429
    assert "Retry-After" in res_exceeded.headers
    retry_after = int(res_exceeded.headers["Retry-After"])
    assert retry_after >= 1

    # 3. User 2 is NOT rate-limited (per-user rate limit)
    res_user2 = await async_client.get("/api/found", cookies=cookies2)
    assert res_user2.status_code == 200
