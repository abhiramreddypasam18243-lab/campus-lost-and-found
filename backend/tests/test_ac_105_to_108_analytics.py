"""Tests for AC-105 to AC-108: Analytics Dashboard (spec section 15)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_token
from app.models.claims import Claim
from app.models.handover import Handover
from app.models.location import CampusLocation
from app.models.report import ItemReport
from app.models.user import Session, User


async def create_user_and_cookie(
    db_session: AsyncSession,
    email: str,
    role: str = "user",
) -> tuple[User, dict[str, str], str]:
    now = datetime.now(UTC)
    user = User(
        email=email,
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$fakehash",
        role=role,
        status="active",
        email_verified_at=now,
    )
    db_session.add(user)
    await db_session.flush()

    raw_sid = f"sess_{uuid.uuid4()}"
    raw_csrf = f"csrf_{uuid.uuid4()}"
    sess = Session(
        user_id=user.id,
        token_hash=hash_token(raw_sid),
        csrf_token_hash=hash_token(raw_csrf),
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
    )
    db_session.add(sess)
    await db_session.commit()

    return user, {"session_id": raw_sid}, raw_csrf


@pytest.mark.asyncio
async def test_ac_105_fixture_metrics(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """AC-105: 10 found reports (4 returned, 2 unclaimed_expired, 4 open).

    recovery_rate = returned / (returned + unclaimed_expired) = 0.667
    unclaimed_rate = unclaimed_expired / total_created = 0.2
    median_time_to_recovery is median of (handover completed - report created).
    """
    base_time = datetime(2026, 3, 1, 10, 0, 0, tzinfo=UTC)

    # 1. Setup location and users
    loc = CampusLocation(
        kind="building",
        name=f"Analytics Hall {uuid.uuid4().hex[:6]}",
    )
    db_session.add(loc)
    await db_session.flush()

    mod_user, mod_cookies, _ = await create_user_and_cookie(
        db_session, f"mod_{uuid.uuid4().hex[:6]}@campus.edu", role="moderator"
    )
    reporter, _, _ = await create_user_and_cookie(
        db_session, f"rep_{uuid.uuid4().hex[:6]}@campus.edu", role="user"
    )
    claimant, _, _ = await create_user_and_cookie(
        db_session, f"claimant_{uuid.uuid4().hex[:6]}@campus.edu", role="user"
    )

    # 2. Create 4 returned reports with completed handovers at +4h, +8h, +12h, +16h
    durations = [4, 8, 12, 16]
    for d in durations:
        created = base_time
        rep = ItemReport(
            type="found",
            status="returned",
            title=f"Returned item {d}h",
            description="Item description for returned item",
            category="electronics",
            time_precision="hour",
            window_start=created,
            window_end=created + timedelta(hours=1),
            location_id=loc.id,
            reporter_id=reporter.id,
            created_at=created,
            updated_at=created + timedelta(hours=d),
        )
        db_session.add(rep)
        await db_session.flush()

        claim = Claim(
            found_id=rep.id,
            claimant_id=claimant.id,
            evidence="Serial number matches",
            status="completed",
        )
        db_session.add(claim)
        await db_session.flush()

        handover = Handover(
            claim_id=claim.id,
            code_hmac="hmac_test_code_digest",
            status="verified",
            issued_at=created,
            expires_at=created + timedelta(hours=48),
            verified_at=created + timedelta(hours=d),
            verified_by_id=mod_user.id,
        )
        db_session.add(handover)

    # 3. Create 2 unclaimed_expired reports
    for i in range(2):
        created = base_time - timedelta(days=95)
        rep = ItemReport(
            type="found",
            status="unclaimed_expired",
            title=f"Expired item {i}",
            description="Unclaimed item left in locker",
            category="books",
            time_precision="day",
            window_start=created,
            window_end=created + timedelta(hours=1),
            location_id=loc.id,
            reporter_id=reporter.id,
            disposition="donated",
            created_at=created,
            updated_at=created + timedelta(days=90),
        )
        db_session.add(rep)

    # 4. Create 4 open reports
    for i in range(4):
        created = base_time + timedelta(hours=i)
        rep = ItemReport(
            type="found",
            status="open",
            title=f"Open item {i}",
            description="Freshly found item",
            category="keys",
            time_precision="hour",
            window_start=created,
            window_end=created + timedelta(hours=1),
            location_id=loc.id,
            reporter_id=reporter.id,
            created_at=created,
            updated_at=created,
        )
        db_session.add(rep)

    await db_session.commit()

    # Query dashboard endpoint as moderator
    resp = await async_client.get("/api/dashboard", cookies=mod_cookies)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # Assert AC-105 counts
    assert data["total_created"] == 10
    assert data["returned_count"] == 4
    assert data["unclaimed_expired_count"] == 2
    assert data["open_count"] == 4

    # Assert AC-105 exact ratios
    # recovery_rate = 4 / (4 + 2) = 0.667
    assert data["recovery_rate"] == 0.667
    # unclaimed_rate = 2 / 10 = 0.2
    assert data["unclaimed_rate"] == 0.2

    # Assert AC-105 median recovery duration: median of [4, 8, 12, 16] = 10.0 hours
    assert data["median_time_to_recovery_hours"] == 10.0


@pytest.mark.asyncio
async def test_ac_106_access_control(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """AC-106: Dashboard available only to moderators and admins; anonymous and regular users get 404."""
    # 1. Unauthenticated request -> 404 anti-enumeration
    resp_anon = await async_client.get("/api/dashboard")
    assert resp_anon.status_code == 404

    # 2. Regular user request -> 404 anti-enumeration
    _, user_cookies, _ = await create_user_and_cookie(
        db_session, f"student_{uuid.uuid4().hex[:6]}@campus.edu", role="user"
    )
    resp_user = await async_client.get("/api/dashboard", cookies=user_cookies)
    assert resp_user.status_code == 404

    # 3. Moderator request -> 200 OK
    _, mod_cookies, _ = await create_user_and_cookie(
        db_session, f"mod_{uuid.uuid4().hex[:6]}@campus.edu", role="moderator"
    )
    resp_mod = await async_client.get("/api/dashboard", cookies=mod_cookies)
    assert resp_mod.status_code == 200

    # 4. Admin request -> 200 OK
    _, admin_cookies, _ = await create_user_and_cookie(
        db_session, f"admin_{uuid.uuid4().hex[:6]}@campus.edu", role="admin"
    )
    resp_admin = await async_client.get("/api/dashboard", cookies=admin_cookies)
    assert resp_admin.status_code == 200


@pytest.mark.asyncio
async def test_ac_107_empty_state(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """AC-107: With no data the dashboard returns zeros or null with status 200 and no errors."""
    _, admin_cookies, _ = await create_user_and_cookie(
        db_session, f"admin_{uuid.uuid4().hex[:6]}@campus.edu", role="admin"
    )

    resp = await async_client.get("/api/dashboard", cookies=admin_cookies)
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_created"] == 0
    assert data["open_count"] == 0
    assert data["returned_count"] == 0
    assert data["unclaimed_expired_count"] == 0
    assert data["recovery_rate"] is None
    assert data["unclaimed_rate"] is None
    assert data["median_time_to_recovery_hours"] is None
    assert data["queue_age_median_hours"] is None


@pytest.mark.asyncio
async def test_ac_108_synthetic_banner(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """AC-108: A banner states when operational metrics come from synthetic demonstration data,

    and that they show the dashboard, not real-world effectiveness.
    """
    _, mod_cookies, _ = await create_user_and_cookie(
        db_session, f"mod_{uuid.uuid4().hex[:6]}@campus.edu", role="moderator"
    )

    resp = await async_client.get("/api/dashboard", cookies=mod_cookies)
    assert resp.status_code == 200
    data = resp.json()

    assert data["is_synthetic_demo"] is True
    banner = data["banner_notice"].lower()
    assert "synthetic" in banner or "demonstration" in banner
    assert "dashboard" in banner
    assert "real-world" in banner
