"""Tests for AC-84 (abuse protection: 3 rejected claims limit to 1 active claim, flagged for mod)

and AC-85 (claims unreviewed after 14 days marked escalated and ordered first).
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claims import Claim
from app.models.location import CampusLocation
from app.models.report import ItemReport
from app.models.user import User


async def create_user_and_cookie(
    async_client: AsyncClient,
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

    from app.core.security import hash_token
    from app.models.user import Session

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


async def create_sample_found_report(
    db_session: AsyncSession, reporter_id: uuid.UUID
) -> ItemReport:
    loc = CampusLocation(name=f"Building {uuid.uuid4().hex[:6]}", kind="building")
    db_session.add(loc)
    await db_session.flush()

    now = datetime.now(UTC)
    report = ItemReport(
        type="found",
        status="open",
        title="Found Backpack",
        description="Black backpack in cafeteria",
        category="bag",
        verification_prompts=[],
        window_start=now,
        window_end=now,
        time_precision="exact",
        location_id=loc.id,
        reporter_id=reporter_id,
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)
    return report


@pytest.mark.asyncio
async def test_ac_84_rejected_claims_limit_to_one_active_and_flag(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC-84: User with 3 rejected claims in 30 days is flagged for moderators and limited to 1 active claim."""
    finder, _, _ = await create_user_and_cookie(async_client, db_session, "finder_rej@campus.edu")
    user, u_cookies, u_csrf = await create_user_and_cookie(
        async_client, db_session, "user_rej@campus.edu"
    )
    mod, mod_cookies, _ = await create_user_and_cookie(
        async_client, db_session, "mod_rej@campus.edu", role="moderator"
    )

    found_reports = [
        await create_sample_found_report(db_session, reporter_id=finder.id) for _ in range(5)
    ]

    now = datetime.now(UTC)

    # Insert 3 rejected claims for this user within the last 10 days
    for i in range(3):
        claim_rej = Claim(
            found_id=found_reports[i].id,
            claimant_id=user.id,
            evidence="Old rejected claim evidence text.",
            answers={},
            image_ids=[],
            status="rejected",
            decision_note="Invalid claim evidence.",
            reviewer_id=mod.id,
            reviewed_at=now - timedelta(days=5),
            submitted_at=now - timedelta(days=6),
            created_at=now - timedelta(days=6),
            updated_at=now - timedelta(days=5),
        )
        db_session.add(claim_rej)
    await db_session.commit()

    headers = {"X-CSRF-Token": u_csrf}

    # 1. User submits 1st active claim -> succeeds
    res1 = await async_client.post(
        "/api/claims",
        json={
            "found_id": str(found_reports[3].id),
            "evidence": "First active claim after 3 rejections.",
            "answers": {},
        },
        cookies=u_cookies,
        headers=headers,
    )
    assert res1.status_code == 201

    # 2. User attempts 2nd active claim -> rejected with 403 (limited to 1 active claim)
    res2 = await async_client.post(
        "/api/claims",
        json={
            "found_id": str(found_reports[4].id),
            "evidence": "Second active claim attempt exceeding limit.",
            "answers": {},
        },
        cookies=u_cookies,
        headers=headers,
    )
    assert res2.status_code == 403
    assert res2.json()["detail"] == "claim_limit_exceeded"

    # 3. Moderator queue shows claimant_flagged=True for this user's claim
    q_res = await async_client.get("/api/mod/queue", cookies=mod_cookies)
    assert q_res.status_code == 200
    items = q_res.json()["items"]
    user_claim_items = [
        it
        for it in items
        if it["item_type"] == "claim" and it["extra_data"]["claimant_id"] == str(user.id)
    ]
    assert len(user_claim_items) == 1
    assert user_claim_items[0]["claimant_flagged"] is True


@pytest.mark.asyncio
async def test_ac_85_unreviewed_claims_escalated_and_sorted_first(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC-85: Claim unreviewed after 14 days is marked escalated and shown first."""
    finder, _, _ = await create_user_and_cookie(async_client, db_session, "finder_esc@campus.edu")
    u1, _, _ = await create_user_and_cookie(async_client, db_session, "u1_esc@campus.edu")
    u2, _, _ = await create_user_and_cookie(async_client, db_session, "u2_esc@campus.edu")
    mod, mod_cookies, _ = await create_user_and_cookie(
        async_client, db_session, "mod_esc@campus.edu", role="moderator"
    )

    found1 = await create_sample_found_report(db_session, reporter_id=finder.id)
    found2 = await create_sample_found_report(db_session, reporter_id=finder.id)

    now = datetime.now(UTC)

    # Claim 1: submitted 2 days ago (not escalated)
    claim_fresh = Claim(
        found_id=found1.id,
        claimant_id=u1.id,
        evidence="Fresh claim evidence submitted 2 days ago.",
        answers={},
        image_ids=[],
        status="submitted",
        submitted_at=now - timedelta(days=2),
        created_at=now - timedelta(days=2),
        updated_at=now - timedelta(days=2),
    )
    db_session.add(claim_fresh)

    # Claim 2: submitted 16 days ago (unreviewed > 14 days -> escalated)
    claim_old = Claim(
        found_id=found2.id,
        claimant_id=u2.id,
        evidence="Old unreviewed claim submitted 16 days ago.",
        answers={},
        image_ids=[],
        status="submitted",
        submitted_at=now - timedelta(days=16),
        created_at=now - timedelta(days=16),
        updated_at=now - timedelta(days=16),
    )
    db_session.add(claim_old)
    await db_session.commit()

    # 1. Inspect claim 2 detail directly: escalated must be True
    res_detail = await async_client.get(f"/api/claims/{claim_old.id}", cookies=mod_cookies)
    assert res_detail.status_code == 200
    assert res_detail.json()["escalated"] is True

    # 2. Inspect claim 1 detail: escalated must be False
    res_fresh = await async_client.get(f"/api/claims/{claim_fresh.id}", cookies=mod_cookies)
    assert res_fresh.status_code == 200
    assert res_fresh.json()["escalated"] is False

    # 3. Check moderator queue order: escalated claim (claim_old) must appear first!
    q_res = await async_client.get("/api/mod/queue", cookies=mod_cookies)
    assert q_res.status_code == 200
    claim_items = [it for it in q_res.json()["items"] if it["item_type"] == "claim"]
    assert len(claim_items) >= 2
    assert claim_items[0]["id"] == str(claim_old.id)
    assert claim_items[0]["escalated"] is True
