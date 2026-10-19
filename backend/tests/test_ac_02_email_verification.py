from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_secure_token, hash_password, hash_token
from app.models.user import EmailToken, User


@pytest.mark.asyncio
async def test_ac_02_email_verification_flow(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC-02: Verification link works once, verifies account; reused or expired returns 410."""
    now = datetime.now(UTC)
    user = User(
        email="verify_test@campus.edu",
        password_hash=hash_password("valid_password_1234"),
        display_name="Verify Tester",
        role="user",
        email_verified_at=None,
    )
    db_session.add(user)
    await db_session.flush()

    raw_token = generate_secure_token()
    token_entry = EmailToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        purpose="verify_email",
        expires_at=now + timedelta(hours=24),
    )
    db_session.add(token_entry)
    await db_session.commit()

    # 1. Valid token verification
    res1 = await async_client.post("/api/auth/verify-email", json={"token": raw_token})
    assert res1.status_code == 200
    assert "verified" in res1.json()["message"].lower()

    # Verify user record updated
    await db_session.refresh(user)
    assert user.email_verified_at is not None

    # 2. Reused token returns 410
    res2 = await async_client.post("/api/auth/verify-email", json={"token": raw_token})
    assert res2.status_code == 410

    # 3. Expired token returns 410
    expired_token = generate_secure_token()
    token_expired = EmailToken(
        user_id=user.id,
        token_hash=hash_token(expired_token),
        purpose="verify_email",
        expires_at=now - timedelta(hours=1),
    )
    db_session.add(token_expired)
    await db_session.commit()

    res3 = await async_client.post("/api/auth/verify-email", json={"token": expired_token})
    assert res3.status_code == 410
