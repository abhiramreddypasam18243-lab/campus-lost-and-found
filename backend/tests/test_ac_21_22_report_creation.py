import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.location import CampusLocation
from app.models.user import User


@pytest.fixture
async def user_auth(db_session: AsyncSession, async_client: AsyncClient) -> dict[str, str]:
    user = User(
        email="student@campus.edu",
        password_hash=hash_password("student_password_123!"),
        role="user",
        email_verified_at=pytest.importorskip("datetime").datetime.now(
            pytest.importorskip("datetime").UTC
        ),
    )
    db_session.add(user)
    await db_session.commit()

    login_res = await async_client.post(
        "/api/auth/login",
        json={"email": "student@campus.edu", "password": "student_password_123!"},
    )
    return {
        "csrf_token": login_res.headers.get("X-CSRF-Token") or login_res.json()["csrf_token"],
        "session_id": login_res.cookies.get("session_id", ""),
    }


@pytest.fixture
async def sample_location(db_session: AsyncSession) -> uuid.UUID:
    loc = CampusLocation(name="East Wing", kind="building")
    db_session.add(loc)
    await db_session.commit()
    return loc.id


@pytest.mark.asyncio
async def test_ac_21_lost_report_validations(
    async_client: AsyncClient, user_auth: dict[str, str], sample_location: uuid.UUID
) -> None:
    headers = {"X-CSRF-Token": user_auth["csrf_token"]}
    cookies = {"session_id": user_auth["session_id"]}

    # 1. Validation error: title too short (< 3), description too short (< 10)
    res_short = await async_client.post(
        "/api/reports/lost",
        json={
            "title": "Hi",
            "description": "Lost it",
            "category": "bottle",
            "location_id": str(sample_location),
            "date": str(date.today()),
            "time_precision": "morning",
        },
        headers=headers,
        cookies=cookies,
    )
    assert res_short.status_code == 422
    errors = res_short.json()["detail"]
    # Check that validation errors list each failing field
    error_fields = [e["loc"][-1] for e in errors]
    assert "title" in error_fields
    assert "description" in error_fields

    # 2. Valid lost report succeeds immediately without waiting for embeddings (AC-21)
    res_valid = await async_client.post(
        "/api/reports/lost",
        json={
            "title": "Hydro Flask Water Bottle",
            "description": "Dark blue 1-liter insulated stainless steel bottle with sticker",
            "category": "bottle",
            "location_id": str(sample_location),
            "date": str(date.today()),
            "time_precision": "afternoon",
        },
        headers=headers,
        cookies=cookies,
    )
    assert res_valid.status_code == 201
    data = res_valid.json()
    assert data["type"] == "lost"
    assert data["status"] == "open"
    assert data["title"] == "Hydro Flask Water Bottle"


@pytest.mark.asyncio
async def test_ac_22_found_report_prompts_and_pending_review(
    async_client: AsyncClient, user_auth: dict[str, str], sample_location: uuid.UUID
) -> None:
    headers = {"X-CSRF-Token": user_auth["csrf_token"]}
    cookies = {"session_id": user_auth["session_id"]}

    # 1. 4th verification prompt returns 422 (max 3 allowed)
    res_4_prompts = await async_client.post(
        "/api/reports/found",
        json={
            "title": "Black Backpack Found",
            "description": "Found on the second floor bench near room 204",
            "category": "bag",
            "location_id": str(sample_location),
            "date": str(date.today()),
            "time_precision": "morning",
            "verification_prompts": [
                "What brand is it?",
                "What is inside the front pouch?",
                "What color is the keychain?",
                "Is there a laptop inside?",
            ],
        },
        headers=headers,
        cookies=cookies,
    )
    assert res_4_prompts.status_code == 422

    # 2. Prompt > 200 chars returns 422
    long_prompt = "A" * 201
    res_long_prompt = await async_client.post(
        "/api/reports/found",
        json={
            "title": "Black Backpack Found",
            "description": "Found on the second floor bench near room 204",
            "category": "bag",
            "location_id": str(sample_location),
            "date": str(date.today()),
            "time_precision": "morning",
            "verification_prompts": [long_prompt],
        },
        headers=headers,
        cookies=cookies,
    )
    assert res_long_prompt.status_code == 422

    # 3. Valid found report starts as pending_review (AC-22)
    res_valid_found = await async_client.post(
        "/api/reports/found",
        json={
            "title": "Black Backpack Found",
            "description": "Found on the second floor bench near room 204",
            "category": "bag",
            "location_id": str(sample_location),
            "date": str(date.today()),
            "time_precision": "morning",
            "private_details": "Contains student ID card for John Doe",
            "verification_prompts": ["What brand is the bag?", "What color is the zipper?"],
        },
        headers=headers,
        cookies=cookies,
    )
    assert res_valid_found.status_code == 201
    data = res_valid_found.json()
    assert data["type"] == "found"
    assert data["status"] == "pending_review"  # AC-22
    assert data["private_details"] == "Contains student ID card for John Doe"
    assert len(data["verification_prompts"]) == 2
