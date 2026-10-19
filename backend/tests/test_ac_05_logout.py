import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User


@pytest.mark.asyncio
async def test_ac_05_logout_session_invalidation(async_client: AsyncClient, db_session: AsyncSession) -> None:
    """AC-05: After logout, the old session cookie returns 401 on protected endpoints."""
    user = User(
        email="logout_test@campus.edu",
        password_hash=hash_password("valid_password_1234"),
        role="user",
    )
    db_session.add(user)
    await db_session.commit()

    # Login to acquire session
    res_login = await async_client.post(
        "/api/auth/login",
        json={"email": "logout_test@campus.edu", "password": "valid_password_1234"},
    )
    assert res_login.status_code == 200
    session_cookie = res_login.cookies.get("session_id")
    assert session_cookie is not None

    csrf_token = res_login.json()["csrf_token"]

    # Verify protected route works with active session
    res_me = await async_client.get("/api/me", cookies={"session_id": session_cookie})
    assert res_me.status_code == 200

    # Logout with valid CSRF token
    res_logout = await async_client.post(
        "/api/auth/logout",
        cookies={"session_id": session_cookie},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert res_logout.status_code == 200

    # Verify old session cookie now returns 401
    res_me_after = await async_client.get("/api/me", cookies={"session_id": session_cookie})
    assert res_me_after.status_code == 401
