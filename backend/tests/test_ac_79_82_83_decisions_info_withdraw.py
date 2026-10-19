"""Tests for AC-79 (decision notes, audit, notification), AC-82 (needs_more_info and resubmission), and AC-83 (claimant withdrawal)."""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.location import CampusLocation
from app.models.notifications import Notification
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
        title="Found Textbook",
        description="Math textbook found in room 101",
        category="book",
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
async def test_ac_79_decision_note_audit_and_notification(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC-79: Approving or rejecting requires note >= 10 chars, writes audit row, creates notification."""
    finder, _, _ = await create_user_and_cookie(async_client, db_session, "finder_dec@campus.edu")
    claimant, c_cookies, c_csrf = await create_user_and_cookie(
        async_client, db_session, "claimant_dec@campus.edu"
    )
    mod, mod_cookies, mod_csrf = await create_user_and_cookie(
        async_client, db_session, "mod_dec@campus.edu", role="moderator"
    )

    found_item = await create_sample_found_report(db_session, reporter_id=finder.id)

    # Submit claim
    c_res = await async_client.post(
        "/api/claims",
        json={
            "found_id": str(found_item.id),
            "evidence": "I left this textbook during morning class.",
            "answers": {},
        },
        cookies=c_cookies,
        headers={"X-CSRF-Token": c_csrf},
    )
    assert c_res.status_code == 201
    claim_id = c_res.json()["id"]

    # Open claim
    await async_client.post(
        f"/api/mod/claims/{claim_id}/open",
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
    )

    # Decision note too short (< 10 chars) -> 422
    short_res = await async_client.post(
        f"/api/mod/claims/{claim_id}/reject",
        json={"decision_note": "Too short"},
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
    )
    assert short_res.status_code == 422

    # Reject with valid decision note
    rej_res = await async_client.post(
        f"/api/mod/claims/{claim_id}/reject",
        json={"decision_note": "Evidence does not match chapter notes inside."},
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
    )
    assert rej_res.status_code == 200
    assert rej_res.json()["status"] == "rejected"

    # Verify audit row created
    audit_stmt = select(AuditLog).where(
        AuditLog.entity_id == uuid.UUID(claim_id),
        AuditLog.action == "claim.rejected",
    )
    audit_row = (await db_session.execute(audit_stmt)).scalar_one_or_none()
    assert audit_row is not None
    assert audit_row.actor_id == mod.id

    # Verify notification created for claimant
    notif_stmt = select(Notification).where(
        Notification.user_id == claimant.id,
        Notification.event_type == "claim_update",
    )
    notif = (await db_session.execute(notif_stmt)).scalar_one_or_none()
    assert notif is not None
    assert notif.payload["claim_status"] == "rejected"


@pytest.mark.asyncio
async def test_ac_82_needs_more_info_resubmission(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC-82: needs_more_info lets claimant add evidence and returns claim to submitted."""
    finder, _, _ = await create_user_and_cookie(async_client, db_session, "finder_info@campus.edu")
    claimant, c_cookies, c_csrf = await create_user_and_cookie(
        async_client, db_session, "claimant_info@campus.edu"
    )
    mod, mod_cookies, mod_csrf = await create_user_and_cookie(
        async_client, db_session, "mod_info@campus.edu", role="moderator"
    )

    found_item = await create_sample_found_report(db_session, reporter_id=finder.id)

    res = await async_client.post(
        "/api/claims",
        json={
            "found_id": str(found_item.id),
            "evidence": "Initial evidence text for my lost book.",
            "answers": {},
        },
        cookies=c_cookies,
        headers={"X-CSRF-Token": c_csrf},
    )
    claim_id = res.json()["id"]

    # Mod opens and requests more info
    await async_client.post(
        f"/api/mod/claims/{claim_id}/open",
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
    )
    req_res = await async_client.post(
        f"/api/mod/claims/{claim_id}/request-info",
        json={"decision_note": "Please specify which name is written on the cover."},
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
    )
    assert req_res.status_code == 200
    assert req_res.json()["status"] == "needs_more_info"

    # Claimant updates evidence with new details
    patch_res = await async_client.patch(
        f"/api/claims/{claim_id}/evidence",
        json={"evidence": "Updated evidence: My student ID 12345 is written on the inside cover."},
        cookies=c_cookies,
        headers={"X-CSRF-Token": c_csrf},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "submitted"
    assert "Updated evidence" in patch_res.json()["evidence"]

    # Claim is back in the queue
    q_res = await async_client.get("/api/mod/queue", cookies=mod_cookies)
    q_ids = [it["id"] for it in q_res.json()["items"]]
    assert claim_id in q_ids


@pytest.mark.asyncio
async def test_ac_83_claimant_withdrawal_before_and_after_approval(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC-83: Withdrawing before approval succeeds; withdrawing after approval returns item to open."""
    finder, _, _ = await create_user_and_cookie(async_client, db_session, "finder_w@campus.edu")
    c1, c1_cookies, c1_csrf = await create_user_and_cookie(
        async_client, db_session, "c1_w@campus.edu"
    )
    c2, c2_cookies, c2_csrf = await create_user_and_cookie(
        async_client, db_session, "c2_w@campus.edu"
    )
    mod, mod_cookies, mod_csrf = await create_user_and_cookie(
        async_client, db_session, "mod_w@campus.edu", role="moderator"
    )

    found1 = await create_sample_found_report(db_session, reporter_id=finder.id)
    found2 = await create_sample_found_report(db_session, reporter_id=finder.id)

    # 1. Withdrawal before approval
    res1 = await async_client.post(
        "/api/claims",
        json={
            "found_id": str(found1.id),
            "evidence": "I thought this was mine but found mine at home.",
            "answers": {},
        },
        cookies=c1_cookies,
        headers={"X-CSRF-Token": c1_csrf},
    )
    claim1_id = res1.json()["id"]

    w1 = await async_client.post(
        f"/api/claims/{claim1_id}/withdraw",
        cookies=c1_cookies,
        headers={"X-CSRF-Token": c1_csrf},
    )
    assert w1.status_code == 200
    assert w1.json()["status"] == "withdrawn"

    # 2. Withdrawal after approval
    res2 = await async_client.post(
        "/api/claims",
        json={
            "found_id": str(found2.id),
            "evidence": "This is definitely my textbook from physics.",
            "answers": {},
        },
        cookies=c2_cookies,
        headers={"X-CSRF-Token": c2_csrf},
    )
    claim2_id = res2.json()["id"]

    # Mod approves
    await async_client.post(
        f"/api/mod/claims/{claim2_id}/open",
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
    )
    await async_client.post(
        f"/api/mod/claims/{claim2_id}/approve",
        json={"decision_note": "Approved claimant evidence."},
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
    )

    # Item is reserved
    await db_session.refresh(found2)
    assert found2.status == "reserved"

    # Claimant withdraws after approval
    w2 = await async_client.post(
        f"/api/claims/{claim2_id}/withdraw",
        cookies=c2_cookies,
        headers={"X-CSRF-Token": c2_csrf},
    )
    assert w2.status_code == 200
    assert w2.json()["status"] == "withdrawn"

    # Found report returns to 'open' (AC-83)
    await db_session.refresh(found2)
    assert found2.status == "open"
