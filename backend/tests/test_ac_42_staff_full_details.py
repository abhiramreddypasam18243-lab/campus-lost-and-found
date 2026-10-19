from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.location import CampusLocation
from app.models.report import ItemImage, ItemReport
from app.models.user import User


@pytest.fixture
async def setup_staff_test(db_session: AsyncSession, async_client: AsyncClient) -> dict[str, any]:
    reporter = User(
        email="student_reporter@campus.edu",
        password_hash=hash_password("Pass1234!"),
        role="user",
        display_name="Alice Student",
        email_verified_at=datetime.now(UTC),
    )
    moderator = User(
        email="moderator_staff@campus.edu",
        password_hash=hash_password("Pass1234!"),
        role="moderator",
        display_name="Mod Staff",
        email_verified_at=datetime.now(UTC),
    )
    admin = User(
        email="admin_staff@campus.edu",
        password_hash=hash_password("Pass1234!"),
        role="admin",
        display_name="Admin Staff",
        email_verified_at=datetime.now(UTC),
    )
    db_session.add_all([reporter, moderator, admin])
    await db_session.commit()

    async def get_cookies(email: str) -> dict[str, str]:
        res = await async_client.post(
            "/api/auth/login",
            json={"email": email, "password": "Pass1234!"},
        )
        return {"session_id": res.cookies.get("session_id", "")}

    campus = CampusLocation(name="North Campus", kind="campus")
    db_session.add(campus)
    await db_session.flush()

    bldg = CampusLocation(name="Admin Building", kind="building", parent_id=campus.id)
    db_session.add(bldg)
    await db_session.flush()

    room = CampusLocation(name="Room 105", kind="room", parent_id=bldg.id)
    db_session.add(room)
    await db_session.commit()

    now = datetime.now(UTC)
    report = ItemReport(
        type="found",
        status="open",
        title="Keys with Leather Fob",
        description="Found brass keys on desk.",
        category="keys",
        location_id=room.id,
        reporter_id=reporter.id,
        window_start=now - timedelta(hours=1),
        window_end=now,
        time_precision="exact",
        private_details="Distinctive blue engraved fob with phone number 555-1234",
        verification_prompts=["What is engraved on the fob?"],
    )
    db_session.add(report)
    await db_session.flush()

    public_img = ItemImage(
        report_id=report.id,
        storage_key="public_keys_key",
        original_mime="image/jpeg",
        sha256="hash1",
        dhash="1111222233334444",
        width=800,
        height=600,
        is_public=True,
    )
    private_img = ItemImage(
        report_id=report.id,
        storage_key="private_keys_engraving_key",
        original_mime="image/jpeg",
        sha256="hash2",
        dhash="5555666677778888",
        width=800,
        height=600,
        is_public=False,
    )
    db_session.add_all([public_img, private_img])
    await db_session.commit()

    return {
        "reporter": reporter,
        "moderator": moderator,
        "admin": admin,
        "report": report,
        "room": room,
        "bldg": bldg,
        "cookies_rep": await get_cookies("student_reporter@campus.edu"),
        "cookies_mod": await get_cookies("moderator_staff@campus.edu"),
        "cookies_adm": await get_cookies("admin_staff@campus.edu"),
    }


@pytest.mark.asyncio
async def test_ac_42_moderator_and_admin_see_full_details(
    async_client: AsyncClient, setup_staff_test: dict[str, any]
) -> None:
    """AC-42: Moderators and admins see full details, including private fields and exact locations."""
    report = setup_staff_test["report"]
    cookies_mod = setup_staff_test["cookies_mod"]
    cookies_adm = setup_staff_test["cookies_adm"]
    cookies_rep = setup_staff_test["cookies_rep"]
    room = setup_staff_test["room"]

    # 1. Moderator check
    res_mod = await async_client.get(f"/api/reports/{report.id}", cookies=cookies_mod)
    assert res_mod.status_code == 200
    mod_data = res_mod.json()

    assert mod_data["private_details"] == "Distinctive blue engraved fob with phone number 555-1234"
    assert mod_data["verification_prompts"] == ["What is engraved on the fob?"]
    assert mod_data["location_id"] == str(room.id)
    assert mod_data["location"]["name"] == "Room 105"
    assert mod_data["reporter"]["email"] == "student_reporter@campus.edu"
    assert len(mod_data["images"]) == 2  # Both public and private images visible!

    # 2. Admin check
    res_adm = await async_client.get(f"/api/reports/{report.id}", cookies=cookies_adm)
    assert res_adm.status_code == 200
    adm_data = res_adm.json()

    assert adm_data["private_details"] == "Distinctive blue engraved fob with phone number 555-1234"
    assert adm_data["verification_prompts"] == ["What is engraved on the fob?"]
    assert adm_data["location_id"] == str(room.id)
    assert adm_data["reporter"]["email"] == "student_reporter@campus.edu"
    assert len(adm_data["images"]) == 2

    # 3. Owner (Reporter) check
    res_rep = await async_client.get(f"/api/reports/{report.id}", cookies=cookies_rep)
    assert res_rep.status_code == 200
    rep_data = res_rep.json()
    assert rep_data["private_details"] == "Distinctive blue engraved fob with phone number 555-1234"
    assert rep_data["verification_prompts"] == ["What is engraved on the fob?"]
    assert rep_data["location_id"] == str(room.id)
