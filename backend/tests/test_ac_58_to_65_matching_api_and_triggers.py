import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.location import CampusLocation
from app.models.matching import MatchCandidate, MatchFeedback
from app.models.notifications import Notification
from app.models.report import ItemReport
from app.models.user import User
from app.services.embeddings import upsert_report_text_embedding
from app.services.matching import compute_matches_for_report


@pytest.fixture
async def matching_scenario(db_session: AsyncSession, async_client: AsyncClient) -> dict[str, any]:
    # 1. Location
    loc = CampusLocation(name="Library Main Hall", kind="building")
    db_session.add(loc)
    await db_session.flush()

    # 2. Users: User A (lost report owner), User B (found report owner), User C (unrelated)
    user_a = User(
        email="student_a@campus.edu",
        password_hash=hash_password("Pass1234!"),
        role="user",
        email_verified_at=datetime.now(UTC),
    )
    user_b = User(
        email="student_b@campus.edu",
        password_hash=hash_password("Pass1234!"),
        role="user",
        email_verified_at=datetime.now(UTC),
    )
    user_c = User(
        email="student_c@campus.edu",
        password_hash=hash_password("Pass1234!"),
        role="user",
        email_verified_at=datetime.now(UTC),
    )
    db_session.add_all([user_a, user_b, user_c])
    await db_session.flush()

    now = datetime.now(UTC)
    canary_string = "CANARY_SECRET_PRIVATE_DETAILS_SERIAL_987654321"

    # 3. Lost Report by User A
    lost_report = ItemReport(
        id=uuid.uuid4(),
        type="lost",
        status="open",
        title="Black ThinkPad Laptop",
        description="ThinkPad T14 with Linux sticker on lid",
        category="laptop_tablet",
        location_id=loc.id,
        reporter_id=user_a.id,
        window_start=now - timedelta(hours=4),
        window_end=now - timedelta(hours=2),
        time_precision="afternoon",
    )

    # 4. Found Report by User B (matching) with private canary details
    found_report = ItemReport(
        id=uuid.uuid4(),
        type="found",
        status="open",
        title="Lenovo ThinkPad Laptop",
        description="Found black Lenovo laptop on table",
        category="laptop_tablet",
        location_id=loc.id,
        reporter_id=user_b.id,
        window_start=now - timedelta(hours=1),
        window_end=now,
        time_precision="afternoon",
        private_details=canary_string,
        verification_prompts=["What OS sticker is on lid?"],
    )

    db_session.add_all([lost_report, found_report])
    await db_session.commit()

    # Create stand-in embeddings for both reports
    await upsert_report_text_embedding(db_session, report=lost_report)
    await upsert_report_text_embedding(db_session, report=found_report)
    await db_session.commit()

    # Login user_a
    login_res = await async_client.post(
        "/api/auth/login",
        json={"email": "student_a@campus.edu", "password": "Pass1234!"},
    )
    cookies_a = {"session_id": login_res.cookies.get("session_id", "")}
    csrf_a = login_res.headers.get("X-CSRF-Token") or login_res.json()["csrf_token"]

    # Login user_c
    login_res_c = await async_client.post(
        "/api/auth/login",
        json={"email": "student_c@campus.edu", "password": "Pass1234!"},
    )
    cookies_c = {"session_id": login_res_c.cookies.get("session_id", "")}
    csrf_c = login_res_c.headers.get("X-CSRF-Token") or login_res_c.json()["csrf_token"]

    return {
        "user_a": user_a,
        "user_b": user_b,
        "user_c": user_c,
        "cookies_a": cookies_a,
        "csrf_a": csrf_a,
        "cookies_c": cookies_c,
        "csrf_c": csrf_c,
        "lost_report": lost_report,
        "found_report": found_report,
        "canary_string": canary_string,
        "location": loc,
    }


@pytest.mark.asyncio
async def test_ac_58_and_60_matches_endpoint_and_privacy_canary(
    async_client: AsyncClient, db_session: AsyncSession, matching_scenario: dict[str, any]
) -> None:
    """AC-58, AC-60: GET /api/reports/{id}/matches:

    - Owner-only (404 for foreign user)
    - Returns candidates with score, bin, signals, explanations
    - Never leaks private details (canary string verification)
    """
    lost_id = matching_scenario["lost_report"].id
    cookies_a = matching_scenario["cookies_a"]
    cookies_c = matching_scenario["cookies_c"]
    canary = matching_scenario["canary_string"]

    # Compute matches
    await compute_matches_for_report(db_session, lost_id)
    await db_session.commit()

    # Foreign user (user C) should get 404
    foreign_res = await async_client.get(f"/api/reports/{lost_id}/matches", cookies=cookies_c)
    assert foreign_res.status_code == 404

    # Owner (user A) gets matches
    res = await async_client.get(f"/api/reports/{lost_id}/matches", cookies=cookies_a)
    assert res.status_code == 200, res.text
    data = res.json()

    assert "matches" in data
    assert len(data["matches"]) >= 1
    match_item = data["matches"][0]

    assert "score" in match_item
    assert "bin" in match_item
    assert "explanation" in match_item
    assert "found_report" in match_item

    # AC-60: Privacy Canary - canary string must NEVER appear in the response payload
    raw_response_text = res.text
    assert canary not in raw_response_text
    assert "verification_prompts" not in raw_response_text
    assert "private_details" not in raw_response_text


@pytest.mark.asyncio
async def test_ac_61_dismiss_match_permanently(
    async_client: AsyncClient, db_session: AsyncSession, matching_scenario: dict[str, any]
) -> None:
    """AC-61: Dismissing a match:

    - Sets status to 'dismissed'
    - Records feedback in match_feedback table
    - Recomputing matches does NOT restore or return the dismissed pair
    """
    lost_id = matching_scenario["lost_report"].id
    cookies_a = matching_scenario["cookies_a"]
    headers_a = {"X-CSRF-Token": matching_scenario["csrf_a"]}

    # Compute matches first
    await compute_matches_for_report(db_session, lost_id)
    await db_session.commit()

    stmt = select(MatchCandidate).where(MatchCandidate.lost_id == lost_id)
    candidate = (await db_session.execute(stmt)).scalars().first()
    assert candidate is not None
    assert candidate.status == "suggested"

    # Dismiss candidate
    dismiss_res = await async_client.post(
        f"/api/matches/{candidate.id}/dismiss",
        cookies=cookies_a,
        headers=headers_a,
    )
    assert dismiss_res.status_code in (200, 204), dismiss_res.text

    # Verify candidate marked as dismissed in DB
    await db_session.refresh(candidate)
    assert candidate.status == "dismissed"

    # Verify match_feedback recorded
    fb_stmt = select(MatchFeedback).where(MatchFeedback.candidate_id == candidate.id)
    feedback = (await db_session.execute(fb_stmt)).scalar_one_or_none()
    assert feedback is not None
    assert feedback.action == "dismissed"

    # Recomputing matches should not return the dismissed pair
    await compute_matches_for_report(db_session, lost_id)
    await db_session.commit()

    res = await async_client.get(f"/api/reports/{lost_id}/matches", cookies=cookies_a)
    assert res.status_code == 200
    active_matches = res.json()["matches"]
    assert not any(m["id"] == str(candidate.id) for m in active_matches)


@pytest.mark.asyncio
async def test_ac_62_ai_advisory_no_state_change_from_score(
    db_session: AsyncSession, matching_scenario: dict[str, any]
) -> None:
    """AC-62: AI is advisory: Setting high score (e.g. 0.99) never changes report status."""
    lost = matching_scenario["lost_report"]
    found = matching_scenario["found_report"]

    initial_lost_status = lost.status
    initial_found_status = found.status

    candidate = MatchCandidate(
        lost_id=lost.id,
        found_id=found.id,
        text_score=0.99,
        image_score=0.99,
        location_score=1.0,
        time_score=1.0,
        combined_score=0.99,
        bin="high",
        weights_version="v1.0",
        model_versions={"text": "all-MiniLM-L6-v2@1"},
        explanation=["Extremely high similarity"],
        status="suggested",
    )
    db_session.add(candidate)
    await db_session.commit()

    await db_session.refresh(lost)
    await db_session.refresh(found)

    assert lost.status == initial_lost_status == "open"
    assert found.status == initial_found_status == "open"


@pytest.mark.asyncio
async def test_ac_63_bidirectional_scoring_and_idempotency(
    db_session: AsyncSession, matching_scenario: dict[str, any]
) -> None:
    """AC-63: Scoring can be triggered from lost or found side and is idempotent."""
    lost_id = matching_scenario["lost_report"].id
    found_id = matching_scenario["found_report"].id

    # 1. Trigger from lost side
    matches_from_lost = await compute_matches_for_report(db_session, lost_id)
    await db_session.commit()
    assert len(matches_from_lost) >= 1

    # Check candidate count
    count_stmt = select(MatchCandidate).where(
        MatchCandidate.lost_id == lost_id, MatchCandidate.found_id == found_id
    )
    records = list((await db_session.execute(count_stmt)).scalars().all())
    assert len(records) == 1

    # 2. Trigger from found side - should not create duplicates (idempotent)
    await compute_matches_for_report(db_session, found_id)
    await db_session.commit()

    records_after = list((await db_session.execute(count_stmt)).scalars().all())
    assert len(records_after) == 1


@pytest.mark.asyncio
async def test_ac_64_weights_versioning_preserves_records(
    db_session: AsyncSession, matching_scenario: dict[str, any]
) -> None:
    """AC-64: Changing weights version preserves earlier results with their version label."""
    lost_id = matching_scenario["lost_report"].id
    found_id = matching_scenario["found_report"].id

    # Compute with default v1.0
    await compute_matches_for_report(db_session, lost_id, weights_version="v1.0")
    await db_session.commit()

    # Compute with new weights version v2.0
    custom_weights = {"text": 0.50, "image": 0.20, "location": 0.20, "time": 0.10}
    await compute_matches_for_report(
        db_session, lost_id, weights=custom_weights, weights_version="v2.0"
    )
    await db_session.commit()

    stmt = select(MatchCandidate).where(
        MatchCandidate.lost_id == lost_id, MatchCandidate.found_id == found_id
    )
    all_versions = list((await db_session.execute(stmt)).scalars().all())
    # Both version records should exist without overwriting
    versions = {c.weights_version for c in all_versions}
    assert "v1.0" in versions
    assert "v2.0" in versions


@pytest.mark.asyncio
async def test_ac_65_notification_created_only_for_high_ranked_matches(
    db_session: AsyncSession, matching_scenario: dict[str, any]
) -> None:
    """AC-65: Notification created only for score >= 0.65 ranked in the top 3."""
    lost_id = matching_scenario["lost_report"].id
    user_a = matching_scenario["user_a"]

    # Compute matches
    matches = await compute_matches_for_report(db_session, lost_id)
    await db_session.commit()

    assert len(matches) >= 1
    top_match = matches[0]

    # Verify notification created if score >= 0.65
    if top_match.combined_score >= 0.65:
        notif_stmt = select(Notification).where(
            Notification.user_id == user_a.id,
            Notification.event_type == "match_suggested",
        )
        notif = (await db_session.execute(notif_stmt)).scalar_one_or_none()
        assert notif is not None
        assert "match_suggested" in notif.event_key
