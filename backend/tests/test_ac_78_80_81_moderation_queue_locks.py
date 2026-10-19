"""Tests for AC-78 (moderator queue and locks), AC-80 (conflict of interest), and AC-81 (single approval per item)."""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

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
        title="Found Umbrella",
        description="Blue umbrella found in lobby",
        category="accessory",
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
async def test_ac_78_moderator_queue_ordering_and_locks(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC-78: Queue ordered by submission time; opening assigns 30m lock preventing other mods."""
    finder, _, _ = await create_user_and_cookie(async_client, db_session, "finder_q@campus.edu")
    c1, c1_cookies, c1_csrf = await create_user_and_cookie(
        async_client, db_session, "c1@campus.edu"
    )
    c2, c2_cookies, c2_csrf = await create_user_and_cookie(
        async_client, db_session, "c2@campus.edu"
    )

    mod1, mod1_cookies, mod1_csrf = await create_user_and_cookie(
        async_client, db_session, "mod1@campus.edu", role="moderator"
    )
    mod2, mod2_cookies, mod2_csrf = await create_user_and_cookie(
        async_client, db_session, "mod2@campus.edu", role="moderator"
    )

    found1 = await create_sample_found_report(db_session, reporter_id=finder.id)
    found2 = await create_sample_found_report(db_session, reporter_id=finder.id)

    # Submit claim 1 earlier, claim 2 later
    res1 = await async_client.post(
        "/api/claims",
        json={
            "found_id": str(found1.id),
            "evidence": "Evidence for first claim submitted.",
            "answers": {},
        },
        cookies=c1_cookies,
        headers={"X-CSRF-Token": c1_csrf},
    )
    assert res1.status_code == 201
    claim1_id = res1.json()["id"]

    res2 = await async_client.post(
        "/api/claims",
        json={
            "found_id": str(found2.id),
            "evidence": "Evidence for second claim submitted.",
            "answers": {},
        },
        cookies=c2_cookies,
        headers={"X-CSRF-Token": c2_csrf},
    )
    assert res2.status_code == 201
    claim2_id = res2.json()["id"]

    # 1. Moderator inspects queue (ordered by submission time)
    q_res = await async_client.get("/api/mod/queue", cookies=mod1_cookies)
    assert q_res.status_code == 200
    q_items = q_res.json()["items"]
    claim_items = [it for it in q_items if it["item_type"] == "claim"]
    assert len(claim_items) >= 2
    assert claim_items[0]["id"] == claim1_id
    assert claim_items[1]["id"] == claim2_id

    # 2. Mod 1 opens claim 1 -> acquires lock for 30 minutes
    lock_res = await async_client.post(
        f"/api/mod/claims/{claim1_id}/open",
        cookies=mod1_cookies,
        headers={"X-CSRF-Token": mod1_csrf},
    )
    assert lock_res.status_code == 200
    claim1_data = lock_res.json()
    assert claim1_data["status"] == "under_review"
    assert claim1_data["locked_by_id"] == str(mod1.id)
    assert claim1_data["lock_expires_at"] is not None

    # 3. Mod 2 attempts to open/decide claim 1 while locked by Mod 1 -> 409 claim_locked
    open_conflict = await async_client.post(
        f"/api/mod/claims/{claim1_id}/open",
        cookies=mod2_cookies,
        headers={"X-CSRF-Token": mod2_csrf},
    )
    assert open_conflict.status_code == 409
    assert open_conflict.json()["detail"] == "claim_locked"

    decide_conflict = await async_client.post(
        f"/api/mod/claims/{claim1_id}/reject",
        json={"decision_note": "Rejection note while locked by other."},
        cookies=mod2_cookies,
        headers={"X-CSRF-Token": mod2_csrf},
    )
    assert decide_conflict.status_code == 409
    assert decide_conflict.json()["detail"] == "claim_locked"

    # 4. Mod 1 (lock owner) can decide it
    decide_ok = await async_client.post(
        f"/api/mod/claims/{claim1_id}/request-info",
        json={"decision_note": "Please provide the serial number of the umbrella."},
        cookies=mod1_cookies,
        headers={"X-CSRF-Token": mod1_csrf},
    )
    assert decide_ok.status_code == 200
    assert decide_ok.json()["status"] == "needs_more_info"


@pytest.mark.asyncio
async def test_ac_80_conflict_of_interest_enforced(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC-80: Moderator cannot decide a claim on an item they reported or a claim they made."""
    mod_reporter, mod_rep_cookies, mod_rep_csrf = await create_user_and_cookie(
        async_client, db_session, "mod_reporter@campus.edu", role="moderator"
    )
    mod_claimant, mod_claim_cookies, mod_claim_csrf = await create_user_and_cookie(
        async_client, db_session, "mod_claimant@campus.edu", role="moderator"
    )
    third_mod, third_cookies, third_csrf = await create_user_and_cookie(
        async_client, db_session, "mod_third@campus.edu", role="moderator"
    )

    found_item = await create_sample_found_report(db_session, reporter_id=mod_reporter.id)

    # Mod claimant files a claim on item reported by Mod reporter
    claim_res = await async_client.post(
        "/api/claims",
        json={
            "found_id": str(found_item.id),
            "evidence": "I claim this item for testing COI.",
            "answers": {},
        },
        cookies=mod_claim_cookies,
        headers={"X-CSRF-Token": mod_claim_csrf},
    )
    assert claim_res.status_code == 201
    claim_id = claim_res.json()["id"]

    # 1. Mod who reported the item tries to decide -> 403 conflict_of_interest
    res_rep = await async_client.post(
        f"/api/mod/claims/{claim_id}/approve",
        json={"decision_note": "Approving item that I reported myself."},
        cookies=mod_rep_cookies,
        headers={"X-CSRF-Token": mod_rep_csrf},
    )
    assert res_rep.status_code == 403
    assert res_rep.json()["detail"] == "conflict_of_interest"

    # 2. Mod who made the claim tries to decide -> 403 conflict_of_interest
    res_claim = await async_client.post(
        f"/api/mod/claims/{claim_id}/approve",
        json={"decision_note": "Approving my own submitted claim here."},
        cookies=mod_claim_cookies,
        headers={"X-CSRF-Token": mod_claim_csrf},
    )
    assert res_claim.status_code == 403
    assert res_claim.json()["detail"] == "conflict_of_interest"

    # 3. Third independent moderator can decide without conflict
    # First transition to under_review
    open_res = await async_client.post(
        f"/api/mod/claims/{claim_id}/open",
        cookies=third_cookies,
        headers={"X-CSRF-Token": third_csrf},
    )
    assert open_res.status_code == 200

    approve_res = await async_client.post(
        f"/api/mod/claims/{claim_id}/approve",
        json={"decision_note": "Approved by independent staff member."},
        cookies=third_cookies,
        headers={"X-CSRF-Token": third_csrf},
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_ac_81_only_one_claim_approved_per_found_item(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC-81: Approving makes found item reserved; approving another while reserved returns 409."""
    finder, _, _ = await create_user_and_cookie(async_client, db_session, "finder_multi@campus.edu")
    c1, c1_cookies, c1_csrf = await create_user_and_cookie(
        async_client, db_session, "user1@campus.edu"
    )
    c2, c2_cookies, c2_csrf = await create_user_and_cookie(
        async_client, db_session, "user2@campus.edu"
    )
    mod, mod_cookies, mod_csrf = await create_user_and_cookie(
        async_client, db_session, "mod_multi@campus.edu", role="moderator"
    )

    found_item = await create_sample_found_report(db_session, reporter_id=finder.id)

    # Both users claim the item
    res1 = await async_client.post(
        "/api/claims",
        json={
            "found_id": str(found_item.id),
            "evidence": "Claim 1 evidence with enough characters.",
            "answers": {},
        },
        cookies=c1_cookies,
        headers={"X-CSRF-Token": c1_csrf},
    )
    assert res1.status_code == 201
    claim1_id = res1.json()["id"]

    res2 = await async_client.post(
        "/api/claims",
        json={
            "found_id": str(found_item.id),
            "evidence": "Claim 2 evidence with enough characters.",
            "answers": {},
        },
        cookies=c2_cookies,
        headers={"X-CSRF-Token": c2_csrf},
    )
    assert res2.status_code == 201
    claim2_id = res2.json()["id"]

    # Mod opens and approves claim 1
    await async_client.post(
        f"/api/mod/claims/{claim1_id}/open",
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
    )
    app1 = await async_client.post(
        f"/api/mod/claims/{claim1_id}/approve",
        json={"decision_note": "Approving claimant 1 after verification."},
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
    )
    assert app1.status_code == 200

    # Found report is now reserved
    await db_session.refresh(found_item)
    assert found_item.status == "reserved"

    # Mod tries to open and approve claim 2 on the same item while reserved -> 409 item_already_reserved
    await async_client.post(
        f"/api/mod/claims/{claim2_id}/open",
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
    )
    app2 = await async_client.post(
        f"/api/mod/claims/{claim2_id}/approve",
        json={"decision_note": "Attempting second approval on reserved item."},
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
    )
    assert app2.status_code == 409
    assert app2.json()["detail"] == "item_already_reserved"
