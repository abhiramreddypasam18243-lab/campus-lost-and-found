"""D-24: AUTO_VERIFY_EMAIL marks new accounts verified at sign-up (demo and dev stacks)."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import auth as auth_api
from app.models.user import EmailToken, User

PAYLOAD = {"email": "auto.verify@campus.edu", "password": "valid_secure_password_1234"}


@pytest.mark.asyncio
async def test_d24_off_by_default_keeps_the_code_flow(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    res = await async_client.post("/api/auth/register", json=PAYLOAD)
    assert res.status_code == 201
    assert res.json()["verified"] is False
    user = (await db_session.execute(select(User))).scalar_one()
    assert user.email_verified_at is None


@pytest.mark.asyncio
async def test_d24_on_verifies_at_signup_without_sending_mail(
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth_api.settings, "AUTO_VERIFY_EMAIL", True)
    sent: list[str] = []

    async def fake_send(*args: object, **kwargs: object) -> None:
        sent.append("mail")

    monkeypatch.setattr(auth_api, "send_verification_email", fake_send)

    res = await async_client.post("/api/auth/register", json=PAYLOAD)
    assert res.status_code == 201
    assert res.json()["verified"] is True
    assert sent == []

    user = (await db_session.execute(select(User))).scalar_one()
    assert user.email_verified_at is not None
    tokens = (await db_session.execute(select(EmailToken))).scalars().all()
    assert tokens == []


@pytest.mark.asyncio
async def test_d24_on_still_enforces_the_domain_list(
    async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(auth_api.settings, "AUTO_VERIFY_EMAIL", True)
    res = await async_client.post(
        "/api/auth/register",
        json={"email": "x@evilcampus.com", "password": "valid_secure_password_1234"},
    )
    assert res.status_code == 422
    assert "email_domain_not_allowed" in str(res.json())


@pytest.mark.asyncio
async def test_d24_auto_verified_user_can_log_in_and_report(
    async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(auth_api.settings, "AUTO_VERIFY_EMAIL", True)
    await async_client.post("/api/auth/register", json=PAYLOAD)
    login = await async_client.post("/api/auth/login", json=PAYLOAD)
    assert login.status_code == 200
    me = await async_client.get("/api/me")
    assert me.json()["email_verified"] is True
