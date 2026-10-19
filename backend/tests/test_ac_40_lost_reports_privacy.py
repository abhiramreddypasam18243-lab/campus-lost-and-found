from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.location import CampusLocation
from app.models.report import ItemReport
from app.models.user import User


@pytest.fixture
async def users_and_roles(db_session: AsyncSession, async_client: AsyncClient) -> dict[str, any]:
    # Reporter (User A)
    user_a = User(
        email="reporter_a@campus.edu",
        password_hash=hash_password("Pass1234!"),
        role="user",
        email_verified_at=datetime.now(UTC),
    )
    # Other Student (User B)
    user_b = User(
        email="student_b@campus.edu",
        password_hash=hash_password("Pass1234!"),
        role="user",
        email_verified_at=datetime.now(UTC),
    )
    # Moderator
    moderator = User(
        email="mod_staff@campus.edu",
        password_hash=hash_password("Pass1234!"),
        role="moderator",
        email_verified_at=datetime.now(UTC),
    )
    # Admin
    admin = User(
        email="admin_staff@campus.edu",
        password_hash=hash_password("Pass1234!"),
        role="admin",
        email_verified_at=datetime.now(UTC),
    )
    db_session.add_all([user_a, user_b, moderator, admin])
    await db_session.commit()

    async def get_cookies(email: str) -> dict[str, str]:
        res = await async_client.post(
            "/api/auth/login",
            json={"email": email, "password": "Pass1234!"},
        )
        return {"session_id": res.cookies.get("session_id", "")}

    return {
        "user_a": user_a,
        "user_b": user_b,
        "moderator": moderator,
        "admin": admin,
        "cookies_a": await get_cookies("reporter_a@campus.edu"),
        "cookies_b": await get_cookies("student_b@campus.edu"),
        "cookies_mod": await get_cookies("mod_staff@campus.edu"),
        "cookies_admin": await get_cookies("admin_staff@campus.edu"),
    }


@pytest.mark.asyncio
async def test_ac_40_lost_reports_privacy(
    async_client: AsyncClient, db_session: AsyncSession, users_and_roles: dict[str, any]
) -> None:
    """AC-40: Lost reports are visible only to their reporter, moderators, and admins."""
    user_a = users_and_roles["user_a"]
    cookies_a = users_and_roles["cookies_a"]
    cookies_b = users_and_roles["cookies_b"]
    cookies_mod = users_and_roles["cookies_mod"]
    cookies_admin = users_and_roles["cookies_admin"]

    loc = CampusLocation(name="Lecture Hall A", kind="building")
    db_session.add(loc)
    await db_session.commit()

    now = datetime.now(UTC)
    lost_report = ItemReport(
        type="lost",
        status="open",
        title="Lost Gold Watch",
        description="Left my gold watch on the front desk of Lecture Hall A.",
        category="jewelry",
        location_id=loc.id,
        reporter_id=user_a.id,
        window_start=now - timedelta(days=1),
        window_end=now,
        time_precision="exact",
        private_details="Engraved with initials A.B. on the back cover",
    )
    db_session.add(lost_report)
    await db_session.commit()

    # 1. Reporter A can see their own lost report (200)
    res_a = await async_client.get(f"/api/reports/{lost_report.id}", cookies=cookies_a)
    assert res_a.status_code == 200
    assert res_a.json()["title"] == "Lost Gold Watch"
    assert res_a.json()["private_details"] == "Engraved with initials A.B. on the back cover"

    # 2. Student B (not owner) requesting User A's lost report returns 404 (anti-enumeration)
    res_b = await async_client.get(f"/api/reports/{lost_report.id}", cookies=cookies_b)
    assert res_b.status_code == 404

    # 3. Unauthenticated request returns 401
    async_client.cookies.clear()
    res_anon = await async_client.get(f"/api/reports/{lost_report.id}")
    assert res_anon.status_code == 401

    # 4. Moderator can see the lost report (200)
    res_mod = await async_client.get(f"/api/reports/{lost_report.id}", cookies=cookies_mod)
    assert res_mod.status_code == 200
    assert res_mod.json()["title"] == "Lost Gold Watch"

    # 5. Admin can see the lost report (200)
    res_admin = await async_client.get(f"/api/reports/{lost_report.id}", cookies=cookies_admin)
    assert res_admin.status_code == 200
    assert res_admin.json()["title"] == "Lost Gold Watch"

    # 6. Lost reports never appear in public found listings
    res_found = await async_client.get("/api/found", cookies=cookies_b)
    assert res_found.status_code == 200
    found_items = res_found.json()["items"]
    assert all(item["id"] != str(lost_report.id) for item in found_items)
