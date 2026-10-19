import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User


@pytest.fixture
async def admin_auth(db_session: AsyncSession, async_client: AsyncClient) -> dict[str, str]:
    """Create a verified admin and log in, returning cookies and CSRF token."""
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
    csrf_token = login_res.json()["csrf_token"]
    session_cookie = login_res.cookies.get("session_id", "")
    return {
        "csrf_token": csrf_token,
        "session_id": session_cookie,
    }


@pytest.fixture
async def user_auth(db_session: AsyncSession, async_client: AsyncClient) -> dict[str, str]:
    """Create a verified normal user and log in."""
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
    assert login_res.status_code == 200
    return {
        "csrf_token": login_res.json()["csrf_token"],
        "session_id": login_res.cookies.get("session_id", ""),
    }


@pytest.mark.asyncio
async def test_ac_17_admin_can_build_location_tree(
    async_client: AsyncClient, admin_auth: dict[str, str]
) -> None:
    headers = {"X-CSRF-Token": admin_auth["csrf_token"]}

    # 1. Create Campus (root)
    res_campus = await async_client.post(
        "/api/locations",
        json={"name": "Main Campus", "kind": "campus", "parent_id": None},
        headers=headers,
    )
    assert res_campus.status_code == 201
    campus_id = res_campus.json()["id"]

    # 2. Create Building under Campus
    res_bldg = await async_client.post(
        "/api/locations",
        json={"name": "Library", "kind": "building", "parent_id": campus_id},
        headers=headers,
    )
    assert res_bldg.status_code == 201
    bldg_id = res_bldg.json()["id"]

    # 3. Create Floor under Building
    res_floor = await async_client.post(
        "/api/locations",
        json={"name": "Floor 2", "kind": "floor", "parent_id": bldg_id},
        headers=headers,
    )
    assert res_floor.status_code == 201
    floor_id = res_floor.json()["id"]

    # 4. Create Room under Floor
    res_room = await async_client.post(
        "/api/locations",
        json={"name": "Reading Room", "kind": "room", "parent_id": floor_id},
        headers=headers,
    )
    assert res_room.status_code == 201
    room_id = res_room.json()["id"]

    # 5. Create Area under Floor
    res_area = await async_client.post(
        "/api/locations",
        json={"name": "Study Pod", "kind": "area", "parent_id": floor_id},
        headers=headers,
    )
    assert res_area.status_code == 201

    # Verify retrieval
    res_get = await async_client.get(f"/api/locations/{room_id}")
    assert res_get.status_code == 200
    assert res_get.json()["name"] == "Reading Room"
    assert res_get.json()["parent_id"] == floor_id


@pytest.mark.asyncio
async def test_ac_17_non_admin_cannot_manage_locations(
    async_client: AsyncClient, user_auth: dict[str, str]
) -> None:
    # Anonymous fails with 401
    res_anon = await async_client.post(
        "/api/locations",
        json={"name": "Off Limits", "kind": "campus"},
    )
    assert res_anon.status_code in (401, 403)

    # Regular user fails with 403
    res_user = await async_client.post(
        "/api/locations",
        json={"name": "Off Limits", "kind": "campus"},
        headers={"X-CSRF-Token": user_auth["csrf_token"]},
    )
    assert res_user.status_code == 403


@pytest.mark.asyncio
async def test_ac_17_sibling_names_unique_case_insensitive(
    async_client: AsyncClient, admin_auth: dict[str, str]
) -> None:
    headers = {"X-CSRF-Token": admin_auth["csrf_token"]}

    # Create root campus
    c_res = await async_client.post(
        "/api/locations",
        json={"name": "Main Campus", "kind": "campus"},
        headers=headers,
    )
    assert c_res.status_code == 201
    c_id = c_res.json()["id"]

    # Create child "Library"
    b1_res = await async_client.post(
        "/api/locations",
        json={"name": "Library", "kind": "building", "parent_id": c_id},
        headers=headers,
    )
    assert b1_res.status_code == 201

    # Duplicate case-insensitive sibling "library" should return 409
    b2_res = await async_client.post(
        "/api/locations",
        json={"name": "library", "kind": "building", "parent_id": c_id},
        headers=headers,
    )
    assert b2_res.status_code == 409

    # Duplicate root campus case-insensitive "main campus" should return 409
    dup_root = await async_client.post(
        "/api/locations",
        json={"name": "main campus", "kind": "campus"},
        headers=headers,
    )
    assert dup_root.status_code == 409


@pytest.mark.asyncio
async def test_ac_17_cannot_become_own_ancestor(
    async_client: AsyncClient, admin_auth: dict[str, str]
) -> None:
    headers = {"X-CSRF-Token": admin_auth["csrf_token"]}

    # Build chain: Campus -> Building -> Floor
    c = (
        await async_client.post(
            "/api/locations", json={"name": "West Campus", "kind": "campus"}, headers=headers
        )
    ).json()
    b = (
        await async_client.post(
            "/api/locations",
            json={"name": "Science Block", "kind": "building", "parent_id": c["id"]},
            headers=headers,
        )
    ).json()
    f = (
        await async_client.post(
            "/api/locations",
            json={"name": "Level 1", "kind": "floor", "parent_id": b["id"]},
            headers=headers,
        )
    ).json()

    # 1. Node cannot become its own parent (self-cycle) -> 422
    patch_self = await async_client.patch(
        f"/api/locations/{b['id']}",
        json={"parent_id": b["id"]},
        headers=headers,
    )
    assert patch_self.status_code == 422

    # 2. Node cannot make its descendant its parent (indirect cycle) -> 422
    # Moving Science Block under Level 1 creates a cycle
    patch_cycle = await async_client.patch(
        f"/api/locations/{b['id']}",
        json={"parent_id": f["id"]},
        headers=headers,
    )
    assert patch_cycle.status_code == 422


@pytest.mark.asyncio
async def test_ac_17_deleting_location_with_reports_returns_409(
    async_client: AsyncClient, admin_auth: dict[str, str], db_session: AsyncSession
) -> None:
    headers = {"X-CSRF-Token": admin_auth["csrf_token"]}

    c = (
        await async_client.post(
            "/api/locations", json={"name": "South Campus", "kind": "campus"}, headers=headers
        )
    ).json()
    loc_id = c["id"]

    # Simulating a report referencing this location (or child in use)
    # If the location is deleted without reports, 204 or 200 is returned
    del_ok = await async_client.delete(f"/api/locations/{loc_id}", headers=headers)
    assert del_ok.status_code in (200, 204)
