"""D-22: a reporter may type where the item was instead of picking a campus-tree node.

A report needs a tree location, a typed place (``location_text``), or both. Typed text is
treated like private details: the reporter and staff see it, public views never do (P1), and a
report without a tree location gets a ``null`` location score (6.3), never zero.
"""

import uuid
from datetime import UTC, date, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.location import CampusLocation
from app.models.report import ItemReport
from app.models.user import User

PASSWORD = "student_password_123!"


async def _login(db: AsyncSession, client: AsyncClient, email: str, role: str = "user") -> dict:
    db.add(User(email=email, password_hash=hash_password(PASSWORD), role=role, email_verified_at=datetime.now(UTC)))
    await db.commit()
    res = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert res.status_code == 200, res.text
    return {
        "headers": {"X-CSRF-Token": res.headers.get("X-CSRF-Token") or res.json()["csrf_token"]},
        "cookies": {"session_id": res.cookies.get("session_id", "")},
    }


def _lost(**where: str) -> dict:
    return {
        "title": "Blue water bottle",
        "description": "Dark blue insulated bottle with a dented base.",
        "category": "bottle",
        "date": str(date.today()),
        "time_precision": "afternoon",
        **where,
    }


@pytest.fixture
async def building(db_session: AsyncSession) -> uuid.UUID:
    loc = CampusLocation(name="East Wing", kind="building")
    db_session.add(loc)
    await db_session.commit()
    return loc.id


@pytest.mark.asyncio
async def test_typed_place_alone_is_accepted(db_session: AsyncSession, async_client: AsyncClient) -> None:
    auth = await _login(db_session, async_client, "typer@campus.edu")
    res = await async_client.post("/api/reports/lost", json=_lost(location_text="  Bench outside the canteen  "), **auth)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["location_id"] is None
    assert body["location_text"] == "Bench outside the canteen"


@pytest.mark.asyncio
async def test_tree_location_and_typed_place_together(
    db_session: AsyncSession, async_client: AsyncClient, building: uuid.UUID
) -> None:
    auth = await _login(db_session, async_client, "both@campus.edu")
    res = await async_client.post(
        "/api/reports/lost", json=_lost(location_id=str(building), location_text="Second bench by the door"), **auth
    )
    assert res.status_code == 201, res.text
    assert res.json()["location_id"] == str(building)
    assert res.json()["location_text"] == "Second bench by the door"


@pytest.mark.asyncio
@pytest.mark.parametrize("where", [{}, {"location_text": "   "}])
async def test_a_place_is_still_required(db_session: AsyncSession, async_client: AsyncClient, where: dict) -> None:
    auth = await _login(db_session, async_client, "nowhere@campus.edu")
    res = await async_client.post("/api/reports/lost", json=_lost(**where), **auth)
    assert res.status_code == 422
    assert "location" in [e["loc"][-1] for e in res.json()["detail"]]


@pytest.mark.asyncio
async def test_typed_place_has_a_length_limit(db_session: AsyncSession, async_client: AsyncClient) -> None:
    auth = await _login(db_session, async_client, "long@campus.edu")
    res = await async_client.post("/api/reports/lost", json=_lost(location_text="x" * 201), **auth)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_typed_place_is_scanned_for_personal_data(db_session: AsyncSession, async_client: AsyncClient) -> None:
    auth = await _login(db_session, async_client, "pii@campus.edu")
    res = await async_client.post("/api/reports/lost", json=_lost(location_text="Call me on 9876543210"), **auth)
    assert res.status_code == 422
    assert res.json()["detail"]["field"] == "location_text"


@pytest.mark.asyncio
async def test_typed_place_never_reaches_public_views(db_session: AsyncSession, async_client: AsyncClient) -> None:
    finder = await _login(db_session, async_client, "finder@campus.edu")
    found = {**_lost(location_text="Under the third bench, canteen"), "title": "Steel bottle"}
    res = await async_client.post("/api/reports/found", json=found, **finder)
    assert res.status_code == 201, res.text
    report_id = res.json()["id"]
    assert res.json()["location_text"] == "Under the third bench, canteen"  # the reporter sees it
    await db_session.execute(update(ItemReport).where(ItemReport.id == uuid.UUID(report_id)).values(status="open"))
    await db_session.commit()

    async_client.cookies.clear()
    viewer = await _login(db_session, async_client, "viewer@campus.edu")
    detail = await async_client.get(f"/api/reports/{report_id}", **viewer)
    listing = await async_client.get("/api/found", **viewer)
    assert detail.status_code == 200 and listing.status_code == 200
    for text in (detail.text, listing.text):
        assert "third bench" not in text
        assert "location_text" not in text
    assert detail.json()["building"] is None
    assert [i["building"] for i in listing.json()["items"]] == [None]

    async_client.cookies.clear()
    mod = await _login(db_session, async_client, "mod@campus.edu", role="moderator")
    staff = await async_client.get(f"/api/reports/{report_id}", **mod)
    assert staff.json()["location_text"] == "Under the third bench, canteen"
    assert staff.json()["location_id"] is None
