from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.location import CampusLocation
from app.models.report import ItemImage, ItemReport
from app.models.user import User


@pytest.mark.asyncio
async def test_ac_39_default_deny_contract_test(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC-39: Public listing and detail responses never leak private fields, verification prompts,

    reporter identity, room/floor locations, private images, or unwhitelisted columns.
    """
    # 1. Setup reporter and viewer (two distinct users)
    reporter = User(
        email="reporter_CANARY_USER@campus.edu",
        password_hash=hash_password("Pass1234!"),
        role="user",
        display_name="Canary Reporter Name",
        email_verified_at=datetime.now(UTC),
    )
    viewer = User(
        email="viewer_student@campus.edu",
        password_hash=hash_password("Pass1234!"),
        role="user",
        display_name="Student Viewer",
        email_verified_at=datetime.now(UTC),
    )
    db_session.add_all([reporter, viewer])
    await db_session.commit()

    # Login as viewer (normal student, not owner)
    login_res = await async_client.post(
        "/api/auth/login",
        json={"email": "viewer_student@campus.edu", "password": "Pass1234!"},
    )
    viewer_cookies = {"session_id": login_res.cookies.get("session_id", "")}

    # 2. Campus hierarchy: Campus -> Building (Science Complex) -> Floor 3 -> Room CANARY_SECRET_ROOM_301
    campus = CampusLocation(name="Main Campus", kind="campus")
    db_session.add(campus)
    await db_session.flush()

    bldg = CampusLocation(name="Science Complex", kind="building", parent_id=campus.id)
    db_session.add(bldg)
    await db_session.flush()

    floor3 = CampusLocation(name="Floor 3", kind="floor", parent_id=bldg.id)
    db_session.add(floor3)
    await db_session.flush()

    room = CampusLocation(name="CANARY_SECRET_ROOM_301", kind="room", parent_id=floor3.id)
    db_session.add(room)
    await db_session.commit()

    # 3. Create open found item with canary strings
    canary_private_details = "CANARY_PRIVATE_STUDENT_ID_99999"
    canary_prompt = "CANARY_VERIFICATION_PROMPT_QUESTION_XYZ"
    canary_private_image_key = "CANARY_PRIVATE_IMAGE_KEY_777"

    now = datetime.now(UTC)
    report = ItemReport(
        type="found",
        status="open",
        title="Public Blue Bottle",
        description="Found water bottle on the table.",
        category="bottle",
        location_id=room.id,
        reporter_id=reporter.id,
        window_start=now - timedelta(hours=1),
        window_end=now,
        time_precision="exact",
        private_details=canary_private_details,
        verification_prompts=[canary_prompt],
    )
    db_session.add(report)
    await db_session.flush()

    # Public image
    public_img = ItemImage(
        report_id=report.id,
        storage_key="public_bottle_image_key",
        original_mime="image/jpeg",
        sha256="hash1",
        dhash="0011223344556677",
        width=640,
        height=480,
        is_public=True,
    )
    # Private image (e.g. detailed view showing ID sticker)
    private_img = ItemImage(
        report_id=report.id,
        storage_key=canary_private_image_key,
        original_mime="image/jpeg",
        sha256="hash2",
        dhash="8899aabbccddeeff",
        width=640,
        height=480,
        is_public=False,
    )
    db_session.add_all([public_img, private_img])
    await db_session.commit()

    # 4. Test listing view: GET /api/found
    res_list = await async_client.get("/api/found", cookies=viewer_cookies)
    assert res_list.status_code == 200
    list_text = res_list.text
    list_json = res_list.json()

    # Canary string checks on listing
    assert canary_private_details not in list_text
    assert canary_prompt not in list_text
    assert canary_private_image_key not in list_text
    assert "CANARY_SECRET_ROOM_301" not in list_text
    assert "reporter_CANARY_USER" not in list_text
    assert "Canary Reporter Name" not in list_text
    assert str(reporter.id) not in list_text
    assert str(room.id) not in list_text
    assert str(floor3.id) not in list_text

    # Whitelist contract check for listing item keys
    item = list_json["items"][0]
    expected_summary_keys = {
        "id",
        "title",
        "category",
        "description",
        "date",
        "building",
        "building_id",
        "thumbnail_url",
        "created_at",
    }
    assert set(item.keys()) == expected_summary_keys, (
        f"Extra or missing keys in public summary: {set(item.keys()) ^ expected_summary_keys}"
    )

    # 5. Test detail view: GET /api/reports/{id} as a non-owner student
    res_detail = await async_client.get(f"/api/reports/{report.id}", cookies=viewer_cookies)
    assert res_detail.status_code == 200
    detail_text = res_detail.text
    detail_json = res_detail.json()

    # Canary string checks on public detail
    assert canary_private_details not in detail_text
    assert canary_prompt not in detail_text
    assert canary_private_image_key not in detail_text
    assert "CANARY_SECRET_ROOM_301" not in detail_text
    assert "reporter_CANARY_USER" not in detail_text
    assert "Canary Reporter Name" not in detail_text
    assert str(reporter.id) not in detail_text
    assert str(room.id) not in detail_text
    assert str(floor3.id) not in detail_text

    # Whitelist contract check for public detail keys
    expected_detail_keys = {
        "id",
        "type",
        "status",
        "title",
        "description",
        "category",
        "date",
        "building",
        "building_id",
        "images",
        "created_at",
    }
    assert set(detail_json.keys()) == expected_detail_keys, (
        f"Extra or missing keys in public detail: {set(detail_json.keys()) ^ expected_detail_keys}"
    )
    # Check that detail images only contain the public image
    assert len(detail_json["images"]) == 1
    assert detail_json["images"][0]["thumbnail_url"] == "/api/images/public_bottle_image_key"
