import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.location import CampusLocation
from app.models.report import ItemReport
from app.models.user import User


@pytest.mark.asyncio
async def test_ac_44_auth_required_and_uuid_structure(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC-44: Listing and detail require a login, and all IDs are unguessable UUIDs."""
    # 1. Unauthenticated requests return 401
    random_uuid = str(uuid.uuid4())
    res_unauth_list = await async_client.get("/api/found")
    assert res_unauth_list.status_code == 401

    res_unauth_detail = await async_client.get(f"/api/reports/{random_uuid}")
    assert res_unauth_detail.status_code == 401

    # 2. Login as verified campus user
    user = User(
        email="student_auth@campus.edu",
        password_hash=hash_password("Pass1234!"),
        role="user",
        email_verified_at=datetime.now(UTC),
    )
    db_session.add(user)
    await db_session.commit()

    login_res = await async_client.post(
        "/api/auth/login",
        json={"email": "student_auth@campus.edu", "password": "Pass1234!"},
    )
    cookies = {"session_id": login_res.cookies.get("session_id", "")}

    # 3. Invalid non-UUID in path parameter returns 422
    res_invalid_uuid = await async_client.get("/api/reports/not-a-uuid-string", cookies=cookies)
    assert res_invalid_uuid.status_code == 422

    # 4. Non-existent UUID returns 404
    non_existent = str(uuid.uuid4())
    res_not_found = await async_client.get(f"/api/reports/{non_existent}", cookies=cookies)
    assert res_not_found.status_code == 404

    # 5. Create a report and verify its ID is a valid RFC 4122 UUIDv4
    loc = CampusLocation(name="Main Gate", kind="building")
    db_session.add(loc)
    await db_session.commit()

    now = datetime.now(UTC)
    report = ItemReport(
        type="found",
        status="open",
        title="Found Keyring",
        description="Found brass keyring with three keys near the gate.",
        category="keys",
        location_id=loc.id,
        reporter_id=user.id,
        window_start=now - timedelta(hours=1),
        window_end=now,
        time_precision="exact",
    )
    db_session.add(report)
    await db_session.commit()

    res_list = await async_client.get("/api/found", cookies=cookies)
    assert res_list.status_code == 200
    items = res_list.json()["items"]
    assert len(items) >= 1

    for item in items:
        # Verify unguessable UUID format
        parsed_uuid = uuid.UUID(item["id"])
        assert parsed_uuid.version == 4
        if item.get("building_id"):
            parsed_bldg = uuid.UUID(item["building_id"])
            assert parsed_bldg.version == 4
