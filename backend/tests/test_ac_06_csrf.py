import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User


@pytest.mark.asyncio
async def test_ac_06_csrf_protection(async_client: AsyncClient, db_session: AsyncSession) -> None:
    """AC-06 (SEC3): State-changing request without valid CSRF returns 403 csrf_failed; GET unaffected."""
    user = User(
        email="csrf_test@campus.edu",
        password_hash=hash_password("valid_password_1234"),
        role="user",
    )
    db_session.add(user)
    await db_session.commit()

    # Login to obtain session cookie and CSRF token
    res_login = await async_client.post(
        "/api/auth/login",
        json={"email": "csrf_test@campus.edu", "password": "valid_password_1234"},
    )
    assert res_login.status_code == 200
    session_cookie = res_login.cookies.get("session_id")
    assert session_cookie is not None
    csrf_token = res_login.json()["csrf_token"]

    # 1. GET requests are unaffected
    res_get = await async_client.get("/api/me", cookies={"session_id": session_cookie})
    assert res_get.status_code == 200

    # 2. POST without CSRF token header returns 403 csrf_failed
    res_post_no_csrf = await async_client.post(
        "/api/auth/logout",
        cookies={"session_id": session_cookie},
    )
    assert res_post_no_csrf.status_code == 403
    assert "csrf_failed" in str(res_post_no_csrf.json())

    # 3. POST with wrong CSRF token returns 403 csrf_failed
    res_post_bad_csrf = await async_client.post(
        "/api/auth/logout",
        cookies={"session_id": session_cookie},
        headers={"X-CSRF-Token": "completely_wrong_csrf_token"},
    )
    assert res_post_bad_csrf.status_code == 403

    # 4. POST with correct CSRF token succeeds
    res_post_good_csrf = await async_client.post(
        "/api/auth/logout",
        cookies={"session_id": session_cookie},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert res_post_good_csrf.status_code == 200
