"""D-25: no emailed code. Sign-up creates a verified account and sends nothing."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import EmailToken, User
from app.services import mailer

PAYLOAD = {"email": "no.otp@campus.edu", "password": "valid_secure_password_1234"}


@pytest.mark.asyncio
async def test_d25_signup_is_verified_and_sends_no_mail(
    async_client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[str] = []

    async def fake_send(*args: object, **kwargs: object) -> None:
        sent.append("mail")

    monkeypatch.setattr(mailer, "send_email", fake_send)

    res = await async_client.post("/api/auth/register", json=PAYLOAD)
    assert res.status_code == 201
    assert sent == []

    user = (await db_session.execute(select(User))).scalar_one()
    assert user.email_verified_at is not None
    assert (await db_session.execute(select(EmailToken))).scalars().all() == []


@pytest.mark.asyncio
async def test_d25_new_user_can_log_in_and_is_verified(async_client: AsyncClient) -> None:
    await async_client.post("/api/auth/register", json=PAYLOAD)
    login = await async_client.post("/api/auth/login", json=PAYLOAD)
    assert login.status_code == 200
    me = await async_client.get("/api/me")
    assert me.json()["email_verified"] is True


@pytest.mark.asyncio
async def test_d25_domain_list_still_applies(async_client: AsyncClient) -> None:
    res = await async_client.post(
        "/api/auth/register",
        json={"email": "x@evilcampus.com", "password": "valid_secure_password_1234"},
    )
    assert res.status_code == 422
    assert "email_domain_not_allowed" in str(res.json())


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/auth/verify-email", "/api/auth/resend-verification"])
async def test_d25_verification_endpoints_are_gone(async_client: AsyncClient, path: str) -> None:
    res = await async_client.post(path, json={"token": "123456"})
    assert res.status_code in (404, 405)
