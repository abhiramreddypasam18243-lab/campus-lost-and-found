import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.domain.categories import ALLOWED_CATEGORIES, is_valid_category
from app.models.location import CampusLocation
from app.models.user import User


@pytest.fixture
async def user_auth(db_session: AsyncSession, async_client: AsyncClient) -> dict[str, str]:
    user = User(
        email="student@campus.edu",
        password_hash=hash_password("student_password_123!"),
        role="user",
        email_verified_at=pytest.importorskip("datetime").datetime.now(
            pytest.importorskip("datetime").UTC
        ),
    )
    db_session.add(user)
    await db_session.commit()

    login_res = await async_client.post(
        "/api/auth/login",
        json={"email": "student@campus.edu", "password": "student_password_123!"},
    )
    return {
        "csrf_token": login_res.headers.get("X-CSRF-Token") or login_res.json()["csrf_token"],
        "session_id": login_res.cookies.get("session_id", ""),
    }


@pytest.fixture
async def sample_location(db_session: AsyncSession) -> uuid.UUID:
    loc = CampusLocation(name="Main Library", kind="building")
    db_session.add(loc)
    await db_session.commit()
    return loc.id


def test_ac_24_allowed_categories_list() -> None:
    expected = [
        "bottle",
        "bag",
        "wallet",
        "phone",
        "laptop_tablet",
        "earphones",
        "keys",
        "id_card",
        "clothing",
        "book",
        "accessory",
        "other",
    ]
    assert ALLOWED_CATEGORIES == expected
    for cat in expected:
        assert is_valid_category(cat) is True
    assert is_valid_category("invalid_cat") is False
    assert is_valid_category("spaceship") is False


@pytest.mark.asyncio
async def test_ac_24_invalid_category_returns_422(
    async_client: AsyncClient, user_auth: dict[str, str], sample_location: uuid.UUID
) -> None:
    headers = {"X-CSRF-Token": user_auth["csrf_token"]}

    # Try creating lost report with an invalid category
    res = await async_client.post(
        "/api/reports/lost",
        json={
            "title": "Lost my hoverboard",
            "description": "Hoverboard was left near library stairs yesterday",
            "category": "hoverboard_invalid",
            "location_id": str(sample_location),
            "date": str(date.today()),
            "time_precision": "day",
        },
        headers=headers,
    )
    assert res.status_code == 422
