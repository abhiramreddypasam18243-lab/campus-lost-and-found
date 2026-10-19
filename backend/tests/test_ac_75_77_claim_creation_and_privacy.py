"""Tests for AC-75 (claim creation validation and limits) and AC-77 (evidence privacy default-deny)."""

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
    verified: bool = True,
) -> tuple[User, dict[str, str], str]:
    now = datetime.now(UTC)
    user = User(
        email=email,
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$fakehash",
        role=role,
        status="active",
        email_verified_at=now if verified else None,
    )
    db_session.add(user)
    await db_session.flush()

    # Create session via direct login or mock session
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

    cookies = {"session_id": raw_sid}
    return user, cookies, raw_csrf


async def create_sample_found_report(
    db_session: AsyncSession,
    reporter_id: uuid.UUID,
    prompts: list[str] | None = None,
    status: str = "open",
) -> ItemReport:
    loc = CampusLocation(name=f"Hall {uuid.uuid4().hex[:6]}", kind="building")
    db_session.add(loc)
    await db_session.flush()

    now = datetime.now(UTC)
    report = ItemReport(
        type="found",
        status=status,
        title="Found Silver Watch",
        description="A silver wrist watch found in library",
        category="accessory",
        private_details="Engraved with initials AB-SECRET",
        verification_prompts=prompts
        if prompts is not None
        else ["What brand is it?", "What color is the strap?"],
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
async def test_ac_75_claim_creation_validation(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC-75: Evidence length 20 to 2000 chars, answers to all prompts, max 3 photos."""
    finder, _, _ = await create_user_and_cookie(async_client, db_session, "finder@campus.edu")
    claimant, cookies, csrf = await create_user_and_cookie(
        async_client, db_session, "claimant@campus.edu"
    )

    found_item = await create_sample_found_report(
        db_session,
        reporter_id=finder.id,
        prompts=["What brand is it?", "What color is the strap?"],
    )

    headers = {"X-CSRF-Token": csrf}

    # 1. Evidence too short (< 20 chars) -> 422
    res = await async_client.post(
        "/api/claims",
        json={
            "found_id": str(found_item.id),
            "evidence": "Short text",
            "answers": {
                "What brand is it?": "Casio",
                "What color is the strap?": "Black",
            },
        },
        cookies=cookies,
        headers=headers,
    )
    assert res.status_code == 422

    # 2. Evidence too long (> 2000 chars) -> 422
    res = await async_client.post(
        "/api/claims",
        json={
            "found_id": str(found_item.id),
            "evidence": "X" * 2001,
            "answers": {
                "What brand is it?": "Casio",
                "What color is the strap?": "Black",
            },
        },
        cookies=cookies,
        headers=headers,
    )
    assert res.status_code == 422

    # 3. Missing answers to verification prompts -> 422
    res = await async_client.post(
        "/api/claims",
        json={
            "found_id": str(found_item.id),
            "evidence": "I lost this exact watch during the exam yesterday.",
            "answers": {
                "What brand is it?": "Casio",
                # missing second prompt
            },
        },
        cookies=cookies,
        headers=headers,
    )
    assert res.status_code == 422

    # 4. Valid claim submission -> 201 Created
    res = await async_client.post(
        "/api/claims",
        json={
            "found_id": str(found_item.id),
            "evidence": "I lost this exact watch during the exam yesterday afternoon.",
            "answers": {
                "What brand is it?": "Casio",
                "What color is the strap?": "Black leather",
            },
        },
        cookies=cookies,
        headers=headers,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "submitted"
    assert data["claimant_id"] == str(claimant.id)
    assert data["found_id"] == str(found_item.id)


@pytest.mark.asyncio
async def test_ac_75_cannot_claim_own_item_or_duplicate(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC-75: Cannot claim own found item, and cannot submit multiple claims for same item."""
    finder, finder_cookies, finder_csrf = await create_user_and_cookie(
        async_client, db_session, "finder_self@campus.edu"
    )
    claimant, claimant_cookies, claimant_csrf = await create_user_and_cookie(
        async_client, db_session, "claimant_unique@campus.edu"
    )

    found_item = await create_sample_found_report(db_session, reporter_id=finder.id, prompts=[])

    # 1. Finder tries to claim their own found item -> 403 cannot_claim_own_report
    res = await async_client.post(
        "/api/claims",
        json={
            "found_id": str(found_item.id),
            "evidence": "Trying to claim my own reported item here.",
            "answers": {},
        },
        cookies=finder_cookies,
        headers={"X-CSRF-Token": finder_csrf},
    )
    assert res.status_code == 403
    assert res.json()["detail"] == "cannot_claim_own_report"

    # 2. Claimant claims once -> 201
    res = await async_client.post(
        "/api/claims",
        json={
            "found_id": str(found_item.id),
            "evidence": "First valid claim for this specific item.",
            "answers": {},
        },
        cookies=claimant_cookies,
        headers={"X-CSRF-Token": claimant_csrf},
    )
    assert res.status_code == 201

    # 3. Claimant attempts duplicate claim on same found item -> 409
    res = await async_client.post(
        "/api/claims",
        json={
            "found_id": str(found_item.id),
            "evidence": "Second claim for the same specific item.",
            "answers": {},
        },
        cookies=claimant_cookies,
        headers={"X-CSRF-Token": claimant_csrf},
    )
    assert res.status_code == 409
    assert res.json()["detail"] == "duplicate_claim_for_item"


@pytest.mark.asyncio
async def test_ac_75_active_claims_limit_enforced(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC-75: A user has at most 3 active claims."""
    finder, _, _ = await create_user_and_cookie(async_client, db_session, "finder_bulk@campus.edu")
    claimant, cookies, csrf = await create_user_and_cookie(
        async_client, db_session, "claimant_active_limit@campus.edu"
    )

    # Create 4 distinct found items
    items = [
        await create_sample_found_report(db_session, reporter_id=finder.id, prompts=[])
        for _ in range(4)
    ]

    headers = {"X-CSRF-Token": csrf}

    # Submit 3 claims successfully
    for i in range(3):
        res = await async_client.post(
            "/api/claims",
            json={
                "found_id": str(items[i].id),
                "evidence": f"Claim evidence for item number {i + 1} here.",
                "answers": {},
            },
            cookies=cookies,
            headers=headers,
        )
        assert res.status_code == 201

    # 4th claim exceeds 3 active claims limit -> 403 claim_limit_exceeded
    res = await async_client.post(
        "/api/claims",
        json={
            "found_id": str(items[3].id),
            "evidence": "Fourth claim evidence exceeding active limit.",
            "answers": {},
        },
        cookies=cookies,
        headers=headers,
    )
    assert res.status_code == 403
    assert res.json()["detail"] == "claim_limit_exceeded"


@pytest.mark.asyncio
async def test_ac_77_evidence_privacy_and_anti_enumeration(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC-77: Evidence visible only to claimant and moderators. Finder and other users get 404."""
    finder, finder_cookies, _ = await create_user_and_cookie(
        async_client, db_session, "finder_priv@campus.edu"
    )
    claimant, claimant_cookies, claimant_csrf = await create_user_and_cookie(
        async_client, db_session, "claimant_priv@campus.edu"
    )
    other_user, other_cookies, _ = await create_user_and_cookie(
        async_client, db_session, "other_priv@campus.edu"
    )
    mod, mod_cookies, _ = await create_user_and_cookie(
        async_client, db_session, "mod_priv@campus.edu", role="moderator"
    )

    found_item = await create_sample_found_report(db_session, reporter_id=finder.id, prompts=[])

    canary = "CANARY_SECRET_EVIDENCE_998811"
    res = await async_client.post(
        "/api/claims",
        json={
            "found_id": str(found_item.id),
            "evidence": f"My secret evidence containing {canary} should not leak.",
            "answers": {},
        },
        cookies=claimant_cookies,
        headers={"X-CSRF-Token": claimant_csrf},
    )
    assert res.status_code == 201
    claim_id = res.json()["id"]

    # 1. Claimant can see their own claim and evidence
    res_claimant = await async_client.get(f"/api/claims/{claim_id}", cookies=claimant_cookies)
    assert res_claimant.status_code == 200
    assert canary in res_claimant.json()["evidence"]

    # 2. Moderator can see the claim and evidence
    res_mod = await async_client.get(f"/api/claims/{claim_id}", cookies=mod_cookies)
    assert res_mod.status_code == 200
    assert canary in res_mod.json()["evidence"]

    # 3. Finder gets 404 (AC-77: finder never sees claim evidence; AC-09: anti-enumeration)
    res_finder = await async_client.get(f"/api/claims/{claim_id}", cookies=finder_cookies)
    assert res_finder.status_code == 404

    # 4. Another random user gets 404
    res_other = await async_client.get(f"/api/claims/{claim_id}", cookies=other_cookies)
    assert res_other.status_code == 404

    # 5. Public browsing of the found item does NOT include canary
    res_found = await async_client.get(f"/api/found/{found_item.id}", cookies=other_cookies)
    assert canary not in res_found.text
