import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.domain.location import LocationNode, calculate_location_score
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
async def test_ac_19_adjacency_symmetric(
    async_client: AsyncClient, admin_auth: dict[str, str]
) -> None:
    headers = {"X-CSRF-Token": admin_auth["csrf_token"]}

    # Create Campus, Library, Student Center
    campus = (
        await async_client.post(
            "/api/locations", json={"name": "Main Campus", "kind": "campus"}, headers=headers
        )
    ).json()
    lib = (
        await async_client.post(
            "/api/locations",
            json={"name": "Library", "kind": "building", "parent_id": campus["id"]},
            headers=headers,
        )
    ).json()
    sc = (
        await async_client.post(
            "/api/locations",
            json={"name": "Student Center", "kind": "building", "parent_id": campus["id"]},
            headers=headers,
        )
    ).json()

    lib_node = LocationNode(
        id=pytest.importorskip("uuid").UUID(lib["id"]),
        name="Library",
        kind="building",
        parent=LocationNode(
            id=pytest.importorskip("uuid").UUID(campus["id"]), name="Main Campus", kind="campus"
        ),
    )
    sc_node = LocationNode(
        id=pytest.importorskip("uuid").UUID(sc["id"]),
        name="Student Center",
        kind="building",
        parent=LocationNode(
            id=pytest.importorskip("uuid").UUID(campus["id"]), name="Main Campus", kind="campus"
        ),
    )

    # Before adjacency, score between Library and Student Center is 0.2 (same campus, not adjacent)
    adjacencies: set[tuple[pytest.importorskip("uuid").UUID, pytest.importorskip("uuid").UUID]] = (
        set()
    )
    assert calculate_location_score(lib_node, sc_node, adjacencies) == 0.2
    assert calculate_location_score(sc_node, lib_node, adjacencies) == 0.2

    # Add adjacency via API
    add_res = await async_client.post(
        "/api/locations/adjacency",
        json={"building_a": lib["id"], "building_b": sc["id"]},
        headers=headers,
    )
    assert add_res.status_code == 201

    # Fetch adjacencies via API
    get_adj = await async_client.get("/api/locations/adjacency")
    assert get_adj.status_code == 200
    adj_list = get_adj.json()
    assert len(adj_list) >= 1

    # When adjacent, both directions score 0.5
    adjacencies.add((lib_node.id, sc_node.id))
    assert calculate_location_score(lib_node, sc_node, adjacencies) == 0.5
    assert calculate_location_score(sc_node, lib_node, adjacencies) == 0.5

    # Remove adjacency
    del_res = await async_client.delete(
        f"/api/locations/adjacency/{lib['id']}/{sc['id']}",
        headers=headers,
    )
    assert del_res.status_code in (200, 204)

    # After removal, score returns to 0.2 in both directions
    adjacencies.clear()
    assert calculate_location_score(lib_node, sc_node, adjacencies) == 0.2
    assert calculate_location_score(sc_node, lib_node, adjacencies) == 0.2


@pytest.mark.asyncio
async def test_ac_19_adjacency_validations(
    async_client: AsyncClient, admin_auth: dict[str, str]
) -> None:
    headers = {"X-CSRF-Token": admin_auth["csrf_token"]}

    campus = (
        await async_client.post(
            "/api/locations", json={"name": "East Campus", "kind": "campus"}, headers=headers
        )
    ).json()
    lib = (
        await async_client.post(
            "/api/locations",
            json={"name": "East Library", "kind": "building", "parent_id": campus["id"]},
            headers=headers,
        )
    ).json()

    # 1. Self adjacency fails with 422
    self_res = await async_client.post(
        "/api/locations/adjacency",
        json={"building_a": lib["id"], "building_b": lib["id"]},
        headers=headers,
    )
    assert self_res.status_code == 422

    # 2. Non-building node fails with 422
    non_bldg_res = await async_client.post(
        "/api/locations/adjacency",
        json={"building_a": campus["id"], "building_b": lib["id"]},
        headers=headers,
    )
    assert non_bldg_res.status_code == 422
