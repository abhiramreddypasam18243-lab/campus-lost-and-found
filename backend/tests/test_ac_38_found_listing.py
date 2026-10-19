from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.location import CampusLocation
from app.models.report import ItemImage, ItemReport
from app.models.user import User


@pytest.fixture
async def setup_data(db_session: AsyncSession, async_client: AsyncClient) -> dict[str, any]:
    # 1. Create a user
    user = User(
        email="viewer@campus.edu",
        password_hash=hash_password("Password_1234!"),
        role="user",
        email_verified_at=datetime.now(UTC),
    )
    db_session.add(user)
    await db_session.commit()

    login_res = await async_client.post(
        "/api/auth/login",
        json={"email": "viewer@campus.edu", "password": "Password_1234!"},
    )
    cookies = {"session_id": login_res.cookies.get("session_id", "")}

    # 2. Campus hierarchy: Campus -> Building (Library) -> Floor 2 -> Room 204
    campus = CampusLocation(name="North Campus", kind="campus")
    db_session.add(campus)
    await db_session.flush()

    library = CampusLocation(name="Library", kind="building", parent_id=campus.id)
    db_session.add(library)
    await db_session.flush()

    floor2 = CampusLocation(name="Floor 2", kind="floor", parent_id=library.id)
    db_session.add(floor2)
    await db_session.flush()

    room204 = CampusLocation(name="Room 204", kind="room", parent_id=floor2.id)
    db_session.add(room204)
    await db_session.commit()

    return {
        "user": user,
        "cookies": cookies,
        "library": library,
        "room204": room204,
    }


@pytest.mark.asyncio
async def test_ac_38_found_listing_shows_only_open_found_items(
    async_client: AsyncClient, db_session: AsyncSession, setup_data: dict[str, any]
) -> None:
    """AC-38: Listing shows only open found items, excluding other states and lost items."""
    user = setup_data["user"]
    cookies = setup_data["cookies"]
    room204 = setup_data["room204"]
    now = datetime.now(UTC)

    # 1. Open found item (SHOULD BE VISIBLE)
    open_found = ItemReport(
        type="found",
        status="open",
        title="Open Blue Backpack",
        description="A durable blue canvas backpack with notebooks inside.",
        category="bag",
        location_id=room204.id,
        reporter_id=user.id,
        window_start=now - timedelta(hours=2),
        window_end=now,
        time_precision="exact",
    )
    db_session.add(open_found)
    await db_session.flush()

    # Add a public image to open_found
    img = ItemImage(
        report_id=open_found.id,
        storage_key="test_public_backpack_image",
        original_mime="image/jpeg",
        sha256="abc1234",
        dhash="0123456789abcdef",
        width=800,
        height=600,
        is_public=True,
    )
    db_session.add(img)

    # 2. Pending review found item (MUST BE EXCLUDED)
    pending_found = ItemReport(
        type="found",
        status="pending_review",
        title="Pending Black Umbrella",
        description="Black umbrella left in foyer.",
        category="umbrella",
        location_id=room204.id,
        reporter_id=user.id,
        window_start=now - timedelta(hours=2),
        window_end=now,
        time_precision="exact",
    )
    db_session.add(pending_found)

    # 3. Removed found item (MUST BE EXCLUDED)
    removed_found = ItemReport(
        type="found",
        status="removed",
        title="Removed Item",
        description="Spam post that got removed by moderator.",
        category="other",
        location_id=room204.id,
        reporter_id=user.id,
        window_start=now - timedelta(hours=2),
        window_end=now,
        time_precision="exact",
    )
    db_session.add(removed_found)

    # 4. Returned found item (MUST BE EXCLUDED)
    returned_found = ItemReport(
        type="found",
        status="returned",
        title="Returned Calculator",
        description="Casio calculator returned to rightful student.",
        category="electronics",
        location_id=room204.id,
        reporter_id=user.id,
        window_start=now - timedelta(hours=2),
        window_end=now,
        time_precision="exact",
    )
    db_session.add(returned_found)

    # 5. Closed found item (MUST BE EXCLUDED)
    closed_found = ItemReport(
        type="found",
        status="closed",
        title="Closed Found Report",
        description="Finder closed this report.",
        category="keys",
        location_id=room204.id,
        reporter_id=user.id,
        window_start=now - timedelta(hours=2),
        window_end=now,
        time_precision="exact",
    )
    db_session.add(closed_found)

    # 6. Open lost item (MUST BE EXCLUDED - lost reports never in public found listing)
    open_lost = ItemReport(
        type="lost",
        status="open",
        title="Lost Laptop Charger",
        description="Lost 65W USB-C charger somewhere in library.",
        category="electronics",
        location_id=room204.id,
        reporter_id=user.id,
        window_start=now - timedelta(hours=2),
        window_end=now,
        time_precision="exact",
    )
    db_session.add(open_lost)
    await db_session.commit()

    # Fetch public found listings
    res = await async_client.get("/api/found", cookies=cookies)
    assert res.status_code == 200, res.text
    data = res.json()
    assert "items" in data
    items = data["items"]

    # Only open_found should be returned
    assert len(items) == 1
    item = items[0]
    assert item["id"] == str(open_found.id)
    assert item["title"] == "Open Blue Backpack"
    assert item["category"] == "bag"
    assert item["description"] == "A durable blue canvas backpack with notebooks inside."
    assert item["building"] == "Library"
    assert item["building_id"] == str(setup_data["library"].id)
    assert item["thumbnail_url"] == "/api/images/test_public_backpack_image"
    assert "date" in item
