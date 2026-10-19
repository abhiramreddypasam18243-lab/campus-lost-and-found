import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User


@pytest.fixture
async def admin_auth(db_session: AsyncSession, async_client: AsyncClient) -> dict[str, str]:
    admin = User(
        email="admin@campus.edu",
        password_hash=hash_password("admin_password_123!"),
        role="admin",
        email_verified_at=pytest.importorskip("datetime").datetime.now(
            pytest.importorskip("datetime").UTC
        ),
    )
    db_session.add(admin)
    await db_session.commit()

    login_res = await async_client.post(
        "/api/auth/login",
        json={"email": "admin@campus.edu", "password": "admin_password_123!"},
    )
    assert login_res.status_code == 200
    return {
        "csrf_token": login_res.headers.get("X-CSRF-Token") or login_res.json()["csrf_token"],
        "session_id": login_res.cookies.get("session_id", ""),
    }


@pytest.mark.asyncio
async def test_ac_20_coordinates_rounded_to_3_decimal_places(
    async_client: AsyncClient, admin_auth: dict[str, str]
) -> None:
    headers = {"X-CSRF-Token": admin_auth["csrf_token"]}

    # Create location with high precision lat/lng: 12.34567 and 77.12389
    res = await async_client.post(
        "/api/locations",
        json={
            "name": "Central Library",
            "kind": "building",
            "lat": 12.34567,
            "lng": 77.12389,
        },
        headers=headers,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["lat"] == 12.346
    assert data["lng"] == 77.124

    # Fetch from database and verify stored values are rounded to 3 decimals
    get_res = await async_client.get(f"/api/locations/{data['id']}")
    assert get_res.status_code == 200
    assert get_res.json()["lat"] == 12.346
    assert get_res.json()["lng"] == 77.124


@pytest.mark.asyncio
async def test_ac_20_optional_coordinates_and_any_level(
    async_client: AsyncClient, admin_auth: dict[str, str]
) -> None:
    headers = {"X-CSRF-Token": admin_auth["csrf_token"]}

    # Building level without coordinates (no GPS required)
    res_bldg = await async_client.post(
        "/api/locations",
        json={
            "name": "Sports Complex",
            "kind": "building",
            "lat": None,
            "lng": None,
        },
        headers=headers,
    )
    assert res_bldg.status_code == 201
    assert res_bldg.json()["lat"] is None
    assert res_bldg.json()["lng"] is None

    # Room level without coordinates
    res_room = await async_client.post(
        "/api/locations",
        json={
            "name": "Badminton Court 1",
            "kind": "room",
            "parent_id": res_bldg.json()["id"],
        },
        headers=headers,
    )
    assert res_room.status_code == 201
    assert res_room.json()["kind"] == "room"
    assert res_room.json()["lat"] is None
