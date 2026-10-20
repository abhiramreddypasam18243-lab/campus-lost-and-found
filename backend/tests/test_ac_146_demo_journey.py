"""Integration test for AC-146: Complete blueprint demo journey.

Covers the full end-to-end lifecycle:
1. Student A reports a lost item with a photo (POST /api/reports/lost, POST /api/reports/{id}/images).
2. Student B reports the same item as found in different words (POST /api/reports/found).
3. Student A views keyword search results (GET /api/reports/browse?q=...).
4. Student A views ranked multimodal matches with explanations (GET /api/reports/{id}/matches).
5. Student A submits a claim on the found item (POST /api/claims).
6. Moderator locks and reviews the claim, approving it (POST /api/mod/claims/{id}/open, approve).
7. Single-use handover code is issued; Moderator completes handover at desk (POST /api/mod/handovers/{claim_id}/verify).
8. Moderator opens the operational analytics dashboard (GET /api/dashboard) confirming completed lifecycle state.
"""

import uuid
from datetime import date
from io import BytesIO

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.location import CampusLocation
from app.models.report import ItemReport
from app.models.user import User
from app.services.embeddings import upsert_report_text_embedding
from app.services.matching import compute_matches_for_report


def create_sample_jpeg() -> bytes:
    """Generate in-memory test JPEG image."""
    img = Image.new("RGB", (100, 100), color=(30, 80, 200))
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_ac_146_full_demo_journey(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    # 0. Setup Campus Location and Users (Student A, Student B, Moderator)
    loc = CampusLocation(name="Central Campus Library", kind="building")
    db_session.add(loc)
    await db_session.flush()

    student_a_pw = "StudentA2026!"
    student_b_pw = "StudentB2026!"
    mod_pw = "Moderator2026!"

    student_a = User(
        email="student_a@campus.edu",
        password_hash=hash_password(student_a_pw),
        role="user",
        status="active",
        email_verified_at=pytest.importorskip("datetime").datetime.now(
            pytest.importorskip("datetime").UTC
        ),
    )
    student_b = User(
        email="student_b@campus.edu",
        password_hash=hash_password(student_b_pw),
        role="user",
        status="active",
        email_verified_at=pytest.importorskip("datetime").datetime.now(
            pytest.importorskip("datetime").UTC
        ),
    )
    moderator = User(
        email="mod@campus.edu",
        password_hash=hash_password(mod_pw),
        role="moderator",
        status="active",
        email_verified_at=pytest.importorskip("datetime").datetime.now(
            pytest.importorskip("datetime").UTC
        ),
    )
    db_session.add_all([student_a, student_b, moderator])
    await db_session.commit()

    # Log in Student A
    login_a = await async_client.post(
        "/api/auth/login",
        json={"email": "student_a@campus.edu", "password": student_a_pw},
    )
    assert login_a.status_code == 200
    cookies_a = {"session_id": login_a.cookies.get("session_id", "")}
    csrf_a = login_a.headers.get("X-CSRF-Token") or login_a.json()["csrf_token"]

    # Log in Student B
    login_b = await async_client.post(
        "/api/auth/login",
        json={"email": "student_b@campus.edu", "password": student_b_pw},
    )
    assert login_b.status_code == 200
    cookies_b = {"session_id": login_b.cookies.get("session_id", "")}
    csrf_b = login_b.headers.get("X-CSRF-Token") or login_b.json()["csrf_token"]

    # Log in Moderator
    login_mod = await async_client.post(
        "/api/auth/login",
        json={"email": "mod@campus.edu", "password": mod_pw},
    )
    assert login_mod.status_code == 200
    cookies_mod = {"session_id": login_mod.cookies.get("session_id", "")}
    csrf_mod = login_mod.headers.get("X-CSRF-Token") or login_mod.json()["csrf_token"]

    # 1. Student A reports a lost item with a photo
    lost_res = await async_client.post(
        "/api/reports/lost",
        json={
            "title": "Lost Matte Black ThinkPad X1",
            "description": "Lost my ThinkPad laptop with an Arch Linux penguin sticker on the bottom left corner.",
            "category": "laptop_tablet",
            "location_id": str(loc.id),
            "date": str(date.today()),
            "time_precision": "morning",
        },
        headers={"X-CSRF-Token": csrf_a},
        cookies=cookies_a,
    )
    assert lost_res.status_code == 201
    lost_data = lost_res.json()
    lost_id = lost_data["id"]

    # Upload photo for Student A's lost report
    img_bytes = create_sample_jpeg()
    upload_res = await async_client.post(
        f"/api/reports/{lost_id}/images",
        files={"file": ("laptop.jpg", img_bytes, "image/jpeg")},
        headers={"X-CSRF-Token": csrf_a},
        cookies=cookies_a,
    )
    assert upload_res.status_code == 201

    # 2. Student B reports the found item in different words
    found_res = await async_client.post(
        "/api/reports/found",
        json={
            "title": "Black Lenovo Notebook Computer",
            "description": "Found a dark Lenovo laptop left on a reading desk in the library study zone.",
            "category": "laptop_tablet",
            "location_id": str(loc.id),
            "date": str(date.today()),
            "time_precision": "morning",
            "verification_prompts": ["What operating system sticker is on the lid?"],
            "private_details": "Serial number: SN-THINKPAD-9941A",
        },
        headers={"X-CSRF-Token": csrf_b},
        cookies=cookies_b,
    )
    assert found_res.status_code == 201
    found_data = found_res.json()
    found_id = found_data["id"]
    # Moderator approves Student B's found report so it becomes listed publicly
    approve_rep_res = await async_client.post(
        f"/api/mod/reports/{found_id}/approve",
        headers={"X-CSRF-Token": csrf_mod},
        cookies=cookies_mod,
    )
    assert approve_rep_res.status_code == 200

    # 3. Student A views keyword search results
    search_res = await async_client.get(
        "/api/found",
        params={"q": "Lenovo laptop"},
        cookies=cookies_a,
    )
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert any(item["id"] == found_id for item in search_data.get("items", []))

    # Compute multimodal embeddings and candidate matching for lost report
    lost_rep_obj = await db_session.get(ItemReport, uuid.UUID(lost_id))
    found_rep_obj = await db_session.get(ItemReport, uuid.UUID(found_id))
    assert lost_rep_obj is not None
    assert found_rep_obj is not None

    await upsert_report_text_embedding(db_session, report=lost_rep_obj)
    await upsert_report_text_embedding(db_session, report=found_rep_obj)
    await db_session.commit()

    await compute_matches_for_report(db_session, uuid.UUID(lost_id))
    await db_session.commit()

    # 4. Student A views ranked matches with explanation
    matches_res = await async_client.get(
        f"/api/reports/{lost_id}/matches",
        cookies=cookies_a,
    )
    assert matches_res.status_code == 200
    matches_data = matches_res.json()
    assert len(matches_data["matches"]) >= 1

    top_match = matches_data["matches"][0]
    assert top_match["found_report"]["id"] == found_id
    assert "explanation" in top_match
    assert top_match["score"] > 0
    # Confirm private canary details did NOT leak
    assert "SN-THINKPAD-9941A" not in matches_res.text

    # 5. Student A submits a claim on the found item
    claim_res = await async_client.post(
        "/api/claims",
        json={
            "found_id": found_id,
            "lost_id": lost_id,
            "evidence": "I can verify the serial number SN-THINKPAD-9941A and Arch Linux sticker.",
            "answers": {"What operating system sticker is on the lid?": "Arch Linux penguin sticker"},
        },
        headers={"X-CSRF-Token": csrf_a},
        cookies=cookies_a,
    )
    assert claim_res.status_code == 201
    claim_id = claim_res.json()["id"]

    # 6. Moderator reviews claim in moderation queue
    # Moderator locks review
    open_lock = await async_client.post(
        f"/api/mod/claims/{claim_id}/open",
        headers={"X-CSRF-Token": csrf_mod},
        cookies=cookies_mod,
    )
    assert open_lock.status_code == 200

    # Moderator approves claim
    approve_res = await async_client.post(
        f"/api/mod/claims/{claim_id}/approve",
        headers={"X-CSRF-Token": csrf_mod},
        cookies=cookies_mod,
        json={"decision_note": "Sticker description and serial match verified."},
    )
    assert approve_res.status_code == 200

    # 7. Student A gets handover code
    claim_view = await async_client.get(
        f"/api/claims/{claim_id}",
        cookies=cookies_a,
    )
    assert claim_view.status_code == 200
    handover_code = claim_view.json()["handover_code"]
    assert handover_code is not None
    assert len(handover_code) == 8

    # Desk verifies code with identity note
    desk_res = await async_client.post(
        f"/api/mod/handovers/{claim_id}/verify",
        headers={"X-CSRF-Token": csrf_mod},
        cookies=cookies_mod,
        json={
            "code": handover_code,
            "identity_note": "Checked student ID card 2026-ENG-042 and verified student identity.",
        },
    )
    assert desk_res.status_code == 200
    desk_data = desk_res.json()
    assert desk_data["status"] == "completed"

    # 8. Open dashboard to verify completed lifecycle state
    dash_res = await async_client.get(
        "/api/dashboard",
        cookies=cookies_mod,
    )
    assert dash_res.status_code == 200
    dash_data = dash_res.json()

    assert "recovery_rate" in dash_data
    assert "total_created" in dash_data
    assert dash_data["total_created"] >= 1
    assert dash_data["returned_count"] >= 1
