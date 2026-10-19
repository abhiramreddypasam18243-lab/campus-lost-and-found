import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, login_rate_limiter
from app.models.user import User


@pytest.mark.asyncio
async def test_ac_04_login_cookie_and_security(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC-04: Login sets HttpOnly, SameSite=Lax cookie; wrong email & wrong password return identical 401."""
    pwd = "secure_test_password_1234"
    user = User(
        email="login_user@campus.edu",
        password_hash=hash_password(pwd),
        display_name="Login User",
        role="user",
        email_verified_at=None,
    )
    db_session.add(user)
    await db_session.commit()

    # 1. Successful login
    res = await async_client.post(
        "/api/auth/login",
        json={"email": "login_user@campus.edu", "password": pwd},
    )
    assert res.status_code == 200
    assert "session_id" in res.cookies
    # Verify cookie directives
    cookie_header = res.headers.get("set-cookie", "")
    assert "httponly" in cookie_header.lower()
    assert "samesite=lax" in cookie_header.lower()

    # 2. SEC5: Identical error response for non-existent email vs wrong password
    res_wrong_email = await async_client.post(
        "/api/auth/login",
        json={"email": "nonexistent@campus.edu", "password": "any_password_1234"},
    )
    assert res_wrong_email.status_code == 401
    err_wrong_email = res_wrong_email.json()

    res_wrong_pwd = await async_client.post(
        "/api/auth/login",
        json={"email": "login_user@campus.edu", "password": "wrong_password_1234"},
    )
    assert res_wrong_pwd.status_code == 401
    err_wrong_pwd = res_wrong_pwd.json()

    assert err_wrong_email == err_wrong_pwd


@pytest.mark.asyncio
async def test_ac_04_login_rate_limiting(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC-04 (SEC6): 6th failed login within 15 minutes returns 429 with Retry-After header."""
    user = User(
        email="ratelimit_target@campus.edu",
        password_hash=hash_password("correct_password_1234"),
        role="user",
    )
    db_session.add(user)
    await db_session.commit()

    login_rate_limiter.reset("ratelimit_target@campus.edu")

    # Perform 5 failed attempts
    for _ in range(5):
        res = await async_client.post(
            "/api/auth/login",
            json={"email": "ratelimit_target@campus.edu", "password": "wrong_password"},
        )
        assert res.status_code == 401

    # 6th attempt must trigger rate limit
    res_6th = await async_client.post(
        "/api/auth/login",
        json={"email": "ratelimit_target@campus.edu", "password": "wrong_password"},
    )
    assert res_6th.status_code == 429
    assert "Retry-After" in res_6th.headers
    assert int(res_6th.headers["Retry-After"]) > 0

    login_rate_limiter.reset("ratelimit_target@campus.edu")
