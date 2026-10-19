from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.location import CampusLocation
from app.models.report import ItemReport
from app.models.user import User


@pytest.fixture
async def search_dataset(db_session: AsyncSession, async_client: AsyncClient) -> dict[str, any]:
    # User
    user = User(
        email="searcher@campus.edu",
        password_hash=hash_password("Pass1234!"),
        role="user",
        email_verified_at=datetime.now(UTC),
    )
    db_session.add(user)
    await db_session.commit()

    login_res = await async_client.post(
        "/api/auth/login",
        json={"email": "searcher@campus.edu", "password": "Pass1234!"},
    )
    cookies = {"session_id": login_res.cookies.get("session_id", "")}

    # Hierarchy:
    # Campus -> Library (bldg_lib) -> Floor 1 -> Room 101
    # Campus -> Science (bldg_sci) -> Floor 2 -> Lab 201
    campus = CampusLocation(name="Central Campus", kind="campus")
    db_session.add(campus)
    await db_session.flush()

    bldg_lib = CampusLocation(name="Main Library", kind="building", parent_id=campus.id)
    bldg_sci = CampusLocation(name="Science Hall", kind="building", parent_id=campus.id)
    db_session.add_all([bldg_lib, bldg_sci])
    await db_session.flush()

    lib_floor1 = CampusLocation(name="Floor 1", kind="floor", parent_id=bldg_lib.id)
    sci_floor2 = CampusLocation(name="Floor 2", kind="floor", parent_id=bldg_sci.id)
    db_session.add_all([lib_floor1, sci_floor2])
    await db_session.flush()

    lib_room101 = CampusLocation(name="Quiet Room 101", kind="room", parent_id=lib_floor1.id)
    sci_lab201 = CampusLocation(name="Chemistry Lab 201", kind="room", parent_id=sci_floor2.id)
    db_session.add_all([lib_room101, sci_lab201])
    await db_session.commit()

    # Seed 5 items with distinct timestamps, locations, categories
    base_time = datetime(2026, 10, 10, 12, 0, 0, tzinfo=UTC)

    # Item 1: In Library Room 101, Bottle, 2026-10-10
    item1 = ItemReport(
        type="found",
        status="open",
        title="Hydroflask Stainless Steel Water Bottle",
        description="Silver metallic thermos found under chair.",
        category="bottle",
        location_id=lib_room101.id,
        reporter_id=user.id,
        window_start=base_time,
        window_end=base_time + timedelta(hours=1),
        time_precision="exact",
        created_at=base_time,
    )
    # Item 2: Directly in Library building, Electronics, 2026-10-12
    item2 = ItemReport(
        type="found",
        status="open",
        title="Apple AirPods Pro Case",
        description="White wireless earbuds charging case, slight scratch on lid.",
        category="electronics",
        location_id=bldg_lib.id,
        reporter_id=user.id,
        window_start=base_time + timedelta(days=2),
        window_end=base_time + timedelta(days=2, hours=1),
        time_precision="exact",
        created_at=base_time + timedelta(days=2),
    )
    # Item 3: In Science Lab 201, Electronics, 2026-10-14
    item3 = ItemReport(
        type="found",
        status="open",
        title="Scientific Graphing Calculator",
        description="Texas Instruments TI-84 Plus, left near sink.",
        category="electronics",
        location_id=sci_lab201.id,
        reporter_id=user.id,
        window_start=base_time + timedelta(days=4),
        window_end=base_time + timedelta(days=4, hours=1),
        time_precision="exact",
        created_at=base_time + timedelta(days=4),
    )
    # Item 4: In Science Hall, Bag, 2026-10-15
    item4 = ItemReport(
        type="found",
        status="open",
        title="Red Gym Duffle Bag",
        description="Red nylon sports bag with silver water bottle logo.",
        category="bag",
        location_id=bldg_sci.id,
        reporter_id=user.id,
        window_start=base_time + timedelta(days=5),
        window_end=base_time + timedelta(days=5, hours=1),
        time_precision="exact",
        created_at=base_time + timedelta(days=5),
    )
    # Item 5: In Library Room 101, Umbrella, 2026-10-16
    item5 = ItemReport(
        type="found",
        status="open",
        title="Compact Yellow Umbrella",
        description="Bright yellow mini umbrella with wooden handle.",
        category="umbrella",
        location_id=lib_room101.id,
        reporter_id=user.id,
        window_start=base_time + timedelta(days=6),
        window_end=base_time + timedelta(days=6, hours=1),
        time_precision="exact",
        created_at=base_time + timedelta(days=6),
    )
    db_session.add_all([item1, item2, item3, item4, item5])
    await db_session.commit()

    return {
        "user": user,
        "cookies": cookies,
        "bldg_lib": bldg_lib,
        "bldg_sci": bldg_sci,
        "item1": item1,
        "item2": item2,
        "item3": item3,
        "item4": item4,
        "item5": item5,
    }


@pytest.mark.asyncio
async def test_ac_41_full_text_search(
    async_client: AsyncClient, search_dataset: dict[str, any]
) -> None:
    """AC-41: Search matches title and description via PostgreSQL full-text search."""
    cookies = search_dataset["cookies"]

    # 1. Search title word "Hydroflask"
    res1 = await async_client.get("/api/found?q=Hydroflask", cookies=cookies)
    assert res1.status_code == 200
    items1 = res1.json()["items"]
    assert len(items1) == 1
    assert items1[0]["id"] == str(search_dataset["item1"].id)

    # 2. Search description phrase "wooden handle" (present only in Item 5)
    res2 = await async_client.get("/api/found?q=wooden handle", cookies=cookies)
    assert res2.status_code == 200
    items2 = res2.json()["items"]
    assert len(items2) == 1
    assert items2[0]["id"] == str(search_dataset["item5"].id)

    # 3. Search word "silver" appears in Item 1 (description) and Item 4 (description)
    res3 = await async_client.get("/api/found?q=silver", cookies=cookies)
    assert res3.status_code == 200
    ids = {item["id"] for item in res3.json()["items"]}
    assert ids == {str(search_dataset["item1"].id), str(search_dataset["item4"].id)}


@pytest.mark.asyncio
async def test_ac_41_filter_by_category_and_building_descendants(
    async_client: AsyncClient, search_dataset: dict[str, any]
) -> None:
    """AC-41: Filters by category and by building (including all descendants)."""
    cookies = search_dataset["cookies"]
    bldg_lib = search_dataset["bldg_lib"]
    bldg_sci = search_dataset["bldg_sci"]

    # 1. Filter by category "electronics" -> should return Item 2 and Item 3
    res_cat = await async_client.get("/api/found?category=electronics", cookies=cookies)
    assert res_cat.status_code == 200
    cat_ids = {item["id"] for item in res_cat.json()["items"]}
    assert cat_ids == {str(search_dataset["item2"].id), str(search_dataset["item3"].id)}

    # 2. Filter by building "Main Library":
    # Item 1 is in Room 101 (descendant of Library), Item 2 is directly in Library, Item 5 is in Room 101.
    res_bldg = await async_client.get(f"/api/found?building_id={bldg_lib.id}", cookies=cookies)
    assert res_bldg.status_code == 200
    bldg_ids = {item["id"] for item in res_bldg.json()["items"]}
    assert bldg_ids == {
        str(search_dataset["item1"].id),
        str(search_dataset["item2"].id),
        str(search_dataset["item5"].id),
    }

    # 3. Filter by building "Science Hall": Item 3 (in Lab 201) and Item 4 (in Science Hall)
    res_sci = await async_client.get(f"/api/found?building_id={bldg_sci.id}", cookies=cookies)
    assert res_sci.status_code == 200
    sci_ids = {item["id"] for item in res_sci.json()["items"]}
    assert sci_ids == {str(search_dataset["item3"].id), str(search_dataset["item4"].id)}


@pytest.mark.asyncio
async def test_ac_41_date_range_and_and_combination(
    async_client: AsyncClient, search_dataset: dict[str, any]
) -> None:
    """AC-41: Filters by date range, and combines all filters with AND."""
    cookies = search_dataset["cookies"]
    bldg_lib = search_dataset["bldg_lib"]

    # 1. Date range: between 2026-10-11 and 2026-10-14 -> Item 2 (10-12) and Item 3 (10-14)
    res_date = await async_client.get(
        "/api/found?date_from=2026-10-11&date_to=2026-10-14", cookies=cookies
    )
    assert res_date.status_code == 200
    date_ids = {item["id"] for item in res_date.json()["items"]}
    assert date_ids == {str(search_dataset["item2"].id), str(search_dataset["item3"].id)}

    # 2. Combine with AND:
    # category=electronics AND building_id=Library -> only Item 2
    res_and = await async_client.get(
        f"/api/found?category=electronics&building_id={bldg_lib.id}", cookies=cookies
    )
    assert res_and.status_code == 200
    and_items = res_and.json()["items"]
    assert len(and_items) == 1
    assert and_items[0]["id"] == str(search_dataset["item2"].id)


@pytest.mark.asyncio
async def test_ac_41_stable_cursor_pagination(
    async_client: AsyncClient, search_dataset: dict[str, any]
) -> None:
    """AC-41: Paginates with a stable cursor and limit."""
    cookies = search_dataset["cookies"]

    # Page 1: limit 2
    res_p1 = await async_client.get("/api/found?limit=2", cookies=cookies)
    assert res_p1.status_code == 200
    p1_data = res_p1.json()
    items_p1 = p1_data["items"]
    cursor1 = p1_data["next_cursor"]

    assert len(items_p1) == 2
    assert cursor1 is not None

    # Page 2: limit 2 with cursor
    res_p2 = await async_client.get(f"/api/found?limit=2&cursor={cursor1}", cookies=cookies)
    assert res_p2.status_code == 200
    p2_data = res_p2.json()
    items_p2 = p2_data["items"]
    cursor2 = p2_data["next_cursor"]

    assert len(items_p2) == 2
    assert cursor2 is not None

    # Page 3: limit 2 with cursor
    res_p3 = await async_client.get(f"/api/found?limit=2&cursor={cursor2}", cookies=cookies)
    assert res_p3.status_code == 200
    p3_data = res_p3.json()
    items_p3 = p3_data["items"]
    cursor3 = p3_data["next_cursor"]

    assert len(items_p3) == 1
    assert cursor3 is None  # Reached the end!

    # Check there are no duplicate IDs across pages
    all_ids = [item["id"] for item in items_p1 + items_p2 + items_p3]
    assert len(all_ids) == 5
    assert len(set(all_ids)) == 5
