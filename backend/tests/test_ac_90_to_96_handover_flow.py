"""Integration tests for AC-90 to AC-96: Handover codes, verification, reissue, and completion."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_token
from app.models.claims import Claim
from app.models.handover import Handover
from app.models.location import CampusLocation
from app.models.report import ItemReport
from app.models.user import Session, User


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


async def create_sample_item_report(
    db_session: AsyncSession,
    reporter_id: uuid.UUID,
    report_type: str = "found",
    title: str = "Sample Item",
) -> ItemReport:
    loc = CampusLocation(name=f"Building {uuid.uuid4().hex[:6]}", kind="building")
    db_session.add(loc)
    await db_session.flush()

    now = datetime.now(UTC)
    report = ItemReport(
        type=report_type,
        status="open",
        title=title,
        description=f"Description for {title}",
        category="electronics",
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
async def test_ac_90_handover_verification_and_duplicate_rejection(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC-90: Desk verification completes handover; re-verifying returns 409 code_used."""
    finder, _, _ = await create_user_and_cookie(async_client, db_session, "finder90@campus.edu")
    claimant, c_cookies, c_csrf = await create_user_and_cookie(
        async_client, db_session, "claimant90@campus.edu"
    )
    mod, mod_cookies, mod_csrf = await create_user_and_cookie(
        async_client, db_session, "mod90@campus.edu", role="moderator"
    )

    found = await create_sample_item_report(db_session, reporter_id=finder.id, title="MacBook Pro")

    # Submit claim
    claim_res = await async_client.post(
        "/api/claims",
        cookies=c_cookies,
        headers={"X-CSRF-Token": c_csrf},
        json={
            "found_id": str(found.id),
            "evidence": "Serial number match: C02X1234ABCD",
            "answers": {},
        },
    )
    assert claim_res.status_code == 201
    claim_id = claim_res.json()["id"]

    # Mod opens and approves claim
    await async_client.post(
        f"/api/mod/claims/{claim_id}/open",
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
    )
    approve_res = await async_client.post(
        f"/api/mod/claims/{claim_id}/approve",
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
        json={"decision_note": "Approved based on serial number verification."},
    )
    assert approve_res.status_code == 200

    # Claimant checks their claim and gets handover code
    claim_view = await async_client.get(f"/api/claims/{claim_id}", cookies=c_cookies)
    assert claim_view.status_code == 200
    handover_code = claim_view.json()["handover_code"]
    assert handover_code is not None
    assert len(handover_code) == 8

    # Desk verifies code with identity note
    desk_res = await async_client.post(
        f"/api/mod/handovers/{claim_id}/verify",
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
        json={
            "code": handover_code,
            "identity_note": "Student ID card matched photo and campus directory.",
        },
    )
    assert desk_res.status_code == 200
    assert desk_res.json()["success"] is True
    assert desk_res.json()["status"] == "completed"

    # Verify found item is now 'returned'
    refreshed_found = await db_session.get(ItemReport, found.id)
    assert refreshed_found.status == "returned"

    # AC-90: Re-verifying the same code returns 409 code_used
    dup_res = await async_client.post(
        f"/api/mod/handovers/{claim_id}/verify",
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
        json={
            "code": handover_code,
            "identity_note": "Second attempt check should fail.",
        },
    )
    assert dup_res.status_code == 409
    assert dup_res.json()["detail"] == "code_used"


@pytest.mark.asyncio
async def test_ac_91_wrong_attempts_and_lockout(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC-91: Handover locks after 5 wrong attempts; 6th attempt returns HTTP 423 handover_locked."""
    finder, _, _ = await create_user_and_cookie(async_client, db_session, "finder91@campus.edu")
    claimant, c_cookies, c_csrf = await create_user_and_cookie(
        async_client, db_session, "claimant91@campus.edu"
    )
    mod, mod_cookies, mod_csrf = await create_user_and_cookie(
        async_client, db_session, "mod91@campus.edu", role="moderator"
    )

    found = await create_sample_item_report(db_session, reporter_id=finder.id, title="Calculator")

    claim_res = await async_client.post(
        "/api/claims",
        cookies=c_cookies,
        headers={"X-CSRF-Token": c_csrf},
        json={
            "found_id": str(found.id),
            "evidence": "TI-84 Plus CE in black case",
            "answers": {},
        },
    )
    claim_id = claim_res.json()["id"]

    await async_client.post(
        f"/api/mod/claims/{claim_id}/open",
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
    )
    await async_client.post(
        f"/api/mod/claims/{claim_id}/approve",
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
        json={"decision_note": "Approved by staff."},
    )

    # 5 wrong attempts
    for attempt in range(1, 6):
        res = await async_client.post(
            f"/api/mod/handovers/{claim_id}/verify",
            cookies=mod_cookies,
            headers={"X-CSRF-Token": mod_csrf},
            json={
                "code": "WRONG123",
                "identity_note": "Photo ID presented and checked.",
            },
        )
        assert res.status_code == 400
        detail = res.json()["detail"]
        assert detail["code"] == "invalid_code"
        assert detail["attempts_left"] == 5 - attempt

    # 6th attempt: locked out with HTTP 423
    locked_res = await async_client.post(
        f"/api/mod/handovers/{claim_id}/verify",
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
        json={
            "code": "WRONG123",
            "identity_note": "Photo ID presented and checked.",
        },
    )
    assert locked_res.status_code == 423
    assert locked_res.json()["detail"] == "handover_locked"


@pytest.mark.asyncio
async def test_ac_92_reissue_limits_and_reset(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC-92: Moderator reissues code, resetting attempts and clock. Max 3 reissues."""
    finder, _, _ = await create_user_and_cookie(async_client, db_session, "finder92@campus.edu")
    claimant, c_cookies, c_csrf = await create_user_and_cookie(
        async_client, db_session, "claimant92@campus.edu"
    )
    mod, mod_cookies, mod_csrf = await create_user_and_cookie(
        async_client, db_session, "mod92@campus.edu", role="moderator"
    )

    found = await create_sample_item_report(db_session, reporter_id=finder.id, title="Water Bottle")

    claim_res = await async_client.post(
        "/api/claims",
        cookies=c_cookies,
        headers={"X-CSRF-Token": c_csrf},
        json={
            "found_id": str(found.id),
            "evidence": "Hydroflask with sticker on the side",
            "answers": {},
        },
    )
    assert claim_res.status_code == 201
    claim_id = claim_res.json()["id"]

    await async_client.post(
        f"/api/mod/claims/{claim_id}/open",
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
    )
    await async_client.post(
        f"/api/mod/claims/{claim_id}/approve",
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
        json={"decision_note": "Approved by moderator after verification."},
    )

    # Waste 2 attempts
    for _ in range(2):
        await async_client.post(
            f"/api/mod/handovers/{claim_id}/verify",
            cookies=mod_cookies,
            headers={"X-CSRF-Token": mod_csrf},
            json={"code": "BADCODE1", "identity_note": "Desk check in progress."},
        )

    # Desk status shows attempts=2
    status_view = await async_client.get(
        f"/api/mod/handovers/{claim_id}",
        cookies=mod_cookies,
    )
    assert status_view.json()["attempts"] == 2
    assert status_view.json()["attempts_left"] == 3

    # Reissue 1: resets attempts to 0
    reissue1 = await async_client.post(
        f"/api/mod/handovers/{claim_id}/reissue",
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
        json={"reason": "Claimant never received original SMS notification."},
    )
    assert reissue1.status_code == 200

    status_view2 = await async_client.get(
        f"/api/mod/handovers/{claim_id}",
        cookies=mod_cookies,
    )
    assert status_view2.json()["attempts"] == 0
    assert status_view2.json()["attempts_left"] == 5
    assert status_view2.json()["reissue_count"] == 1

    # Reissue 2 and 3
    reissue2 = await async_client.post(
        f"/api/mod/handovers/{claim_id}/reissue",
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
        json={"reason": "Second reissue due to email client quarantine."},
    )
    assert reissue2.status_code == 200

    reissue3 = await async_client.post(
        f"/api/mod/handovers/{claim_id}/reissue",
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
        json={"reason": "Third reissue requested in person at the desk."},
    )
    assert reissue3.status_code == 200

    # 4th reissue exceeds max allowed (max 3 reissues per AC-92)
    reissue4 = await async_client.post(
        f"/api/mod/handovers/{claim_id}/reissue",
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
        json={"reason": "Attempting fourth reissue which should be blocked."},
    )
    assert reissue4.status_code == 409
    assert reissue4.json()["detail"] == "reissue_limit_exceeded"


@pytest.mark.asyncio
async def test_ac_93_atomic_completion_transaction(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC-93: Handover verification completes claim, marks found item returned,

    resolves linked lost report, and rejects competing claims with 'item_returned'.
    """
    finder, _, _ = await create_user_and_cookie(async_client, db_session, "finder93@campus.edu")
    c1, c1_cookies, c1_csrf = await create_user_and_cookie(
        async_client, db_session, "claimant93_1@campus.edu"
    )
    c2, c2_cookies, c2_csrf = await create_user_and_cookie(
        async_client, db_session, "claimant93_2@campus.edu"
    )
    mod, mod_cookies, mod_csrf = await create_user_and_cookie(
        async_client, db_session, "mod93@campus.edu", role="moderator"
    )

    found = await create_sample_item_report(db_session, reporter_id=finder.id, title="iPhone 15")
    lost = await create_sample_item_report(
        db_session, reporter_id=c1.id, report_type="lost", title="Lost iPhone 15"
    )

    # C1 submits claim linked to lost report
    c1_res = await async_client.post(
        "/api/claims",
        cookies=c1_cookies,
        headers={"X-CSRF-Token": c1_csrf},
        json={
            "found_id": str(found.id),
            "lost_id": str(lost.id),
            "evidence": "Lock screen has photo of my golden retriever.",
            "answers": {},
        },
    )
    c1_claim_id = c1_res.json()["id"]

    # C2 submits competing claim
    c2_res = await async_client.post(
        "/api/claims",
        cookies=c2_cookies,
        headers={"X-CSRF-Token": c2_csrf},
        json={
            "found_id": str(found.id),
            "evidence": "Mine is black 256GB.",
            "answers": {},
        },
    )
    c2_claim_id = c2_res.json()["id"]

    # Mod approves C1
    await async_client.post(
        f"/api/mod/claims/{c1_claim_id}/open",
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
    )
    await async_client.post(
        f"/api/mod/claims/{c1_claim_id}/approve",
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
        json={"decision_note": "Lock screen photo verified."},
    )

    # C1 gets code and mod verifies it
    c1_view = await async_client.get(f"/api/claims/{c1_claim_id}", cookies=c1_cookies)
    code = c1_view.json()["handover_code"]

    verify_res = await async_client.post(
        f"/api/mod/handovers/{c1_claim_id}/verify",
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
        json={"code": code, "identity_note": "Government ID inspected and matched claimant."},
    )
    assert verify_res.status_code == 200

    # 1. C1 claim is 'completed'
    claim1 = await db_session.get(Claim, uuid.UUID(c1_claim_id))
    assert claim1.status == "completed"

    # 2. Found report is 'returned'
    found_refreshed = await db_session.get(ItemReport, found.id)
    assert found_refreshed.status == "returned"

    # 3. Linked lost report is 'resolved'
    lost_refreshed = await db_session.get(ItemReport, lost.id)
    assert lost_refreshed.status == "resolved"

    # 4. Competing C2 claim is 'rejected' with 'item_returned'
    claim2 = await db_session.get(Claim, uuid.UUID(c2_claim_id))
    assert claim2.status == "rejected"
    assert claim2.decision_note == "item_returned"


@pytest.mark.asyncio
async def test_ac_94_expiry_sweep(async_client: AsyncClient, db_session: AsyncSession) -> None:
    """AC-94: When code expires unused, claim expires and found item returns to open."""
    finder, _, _ = await create_user_and_cookie(async_client, db_session, "finder94@campus.edu")
    claimant, c_cookies, c_csrf = await create_user_and_cookie(
        async_client, db_session, "claimant94@campus.edu"
    )
    mod, mod_cookies, mod_csrf = await create_user_and_cookie(
        async_client, db_session, "mod94@campus.edu", role="moderator"
    )

    found = await create_sample_item_report(db_session, reporter_id=finder.id, title="Watch")

    claim_res = await async_client.post(
        "/api/claims",
        cookies=c_cookies,
        headers={"X-CSRF-Token": c_csrf},
        json={
            "found_id": str(found.id),
            "evidence": "Casio vintage watch with silver strap",
            "answers": {},
        },
    )
    assert claim_res.status_code == 201
    claim_id = claim_res.json()["id"]

    await async_client.post(
        f"/api/mod/claims/{claim_id}/open",
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
    )
    await async_client.post(
        f"/api/mod/claims/{claim_id}/approve",
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
        json={"decision_note": "Approved by moderator after verification."},
    )

    # Artificially set handover expiration to 1 hour in the past
    await db_session.rollback()
    stmt = select(Handover).where(Handover.claim_id == uuid.UUID(claim_id))
    handover = (await db_session.execute(stmt)).scalar_one()
    handover.expires_at = datetime.now(UTC) - timedelta(hours=1)
    await db_session.commit()

    # Trigger expire endpoint
    sweep_res = await async_client.post(
        "/api/mod/handovers/expire",
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
    )
    assert sweep_res.status_code == 200
    assert sweep_res.json()["expired_count"] >= 1

    # Claim should be expired
    await db_session.rollback()
    claim = await db_session.get(Claim, uuid.UUID(claim_id))
    assert claim.status == "expired"

    # Found report should return to 'open'
    found_item = await db_session.get(ItemReport, found.id)
    assert found_item.status == "open"


@pytest.mark.asyncio
async def test_ac_96_privacy_guarantee(async_client: AsyncClient, db_session: AsyncSession) -> None:
    """AC-96: Claimant sees code; moderator and desk views NEVER reveal code or HMAC."""
    finder, _, _ = await create_user_and_cookie(async_client, db_session, "finder96@campus.edu")
    claimant, c_cookies, c_csrf = await create_user_and_cookie(
        async_client, db_session, "claimant96@campus.edu"
    )
    mod, mod_cookies, mod_csrf = await create_user_and_cookie(
        async_client, db_session, "mod96@campus.edu", role="moderator"
    )
    unrelated, u_cookies, _ = await create_user_and_cookie(
        async_client, db_session, "unrelated96@campus.edu"
    )

    found = await create_sample_item_report(db_session, reporter_id=finder.id, title="Keys")

    claim_res = await async_client.post(
        "/api/claims",
        cookies=c_cookies,
        headers={"X-CSRF-Token": c_csrf},
        json={
            "found_id": str(found.id),
            "evidence": "Subaru key fob with blue ring",
            "answers": {},
        },
    )
    assert claim_res.status_code == 201
    claim_id = claim_res.json()["id"]

    await async_client.post(
        f"/api/mod/claims/{claim_id}/open",
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
    )
    await async_client.post(
        f"/api/mod/claims/{claim_id}/approve",
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
        json={"decision_note": "Key fob matches."},
    )

    # 1. Claimant receives code
    claimant_view = await async_client.get(f"/api/claims/{claim_id}", cookies=c_cookies)
    assert claimant_view.status_code == 200
    assert claimant_view.json()["handover_code"] is not None

    # 2. Moderator viewing claim does NOT receive code
    mod_view = await async_client.get(f"/api/claims/{claim_id}", cookies=mod_cookies)
    assert mod_view.status_code == 200
    assert mod_view.json()["handover_code"] is None

    # 3. Desk status view never contains 'code', 'handover_code', or 'code_hmac'
    desk_view = await async_client.get(f"/api/mod/handovers/{claim_id}", cookies=mod_cookies)
    assert desk_view.status_code == 200
    desk_data = desk_view.json()
    assert "code" not in desk_data
    assert "handover_code" not in desk_data
    assert "code_hmac" not in desk_data

    # 4. Unrelated user gets 404 anti-enumeration
    unrelated_view = await async_client.get(f"/api/claims/{claim_id}", cookies=u_cookies)
    assert unrelated_view.status_code == 404
