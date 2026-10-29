import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


@pytest.mark.asyncio
async def test_ac_01_registration_success(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC-01 / D-25: Valid campus email creates a verified account with Argon2id hash; password not returned."""
    payload = {
        "email": "student1@campus.edu",
        "password": "valid_secure_password_1234",
        "display_name": "Test Student",
    }
    response = await async_client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert data["email"] == "student1@campus.edu"
    assert "password" not in data
    assert "password_hash" not in data

    # Verify database state
    stmt = select(User).where(User.email == "student1@campus.edu")
    user = (await db_session.execute(stmt)).scalar_one_or_none()
    assert user is not None
    assert user.password_hash.startswith("$argon2id$")
    assert user.email_verified_at is not None
    assert user.role == "user"


@pytest.mark.asyncio
async def test_ac_01_registration_disallowed_domain(async_client: AsyncClient) -> None:
    """AC-01: Email outside ALLOWED_EMAIL_DOMAINS returns 422 email_domain_not_allowed."""
    payload = {
        "email": "stranger@gmail.com",
        "password": "valid_secure_password_1234",
    }
    response = await async_client.post("/api/auth/register", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert "email_domain_not_allowed" in str(data)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "email",
    [
        "stranger@evilcampus.com",  # keyword in name, not a whitelisted domain
        "stranger@freeschool.xyz",
        "stranger@other-university.edu",  # academic suffix, not a whitelisted domain
        "stranger@campus.edu.attacker.net",  # whitelisted domain as a prefix
    ],
)
async def test_ac_01_registration_lookalike_domains_rejected(
    async_client: AsyncClient, email: str
) -> None:
    """AC-01 / P5: only exact ALLOWED_EMAIL_DOMAINS entries register; look-alikes return 422."""
    payload = {"email": email, "password": "valid_secure_password_1234"}
    response = await async_client.post("/api/auth/register", json=payload)
    assert response.status_code == 422
    assert "email_domain_not_allowed" in str(response.json())


@pytest.mark.asyncio
async def test_ac_01_registration_duplicate_email(async_client: AsyncClient) -> None:
    """AC-01: Duplicate email (compared case-insensitively) returns 409."""
    payload1 = {
        "email": "unique.user@campus.edu",
        "password": "valid_secure_password_1234",
    }
    res1 = await async_client.post("/api/auth/register", json=payload1)
    assert res1.status_code == 201

    # Try duplicate with mixed case
    payload2 = {
        "email": "UNIQUE.USER@campus.edu",
        "password": "another_valid_password_5678",
    }
    res2 = await async_client.post("/api/auth/register", json=payload2)
    assert res2.status_code == 409
    data = res2.json()
    assert "email_already_registered" in str(data)
