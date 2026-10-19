import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.domain.pii import luhn_check, scan_pii
from app.models.location import CampusLocation
from app.models.user import User


def test_ac_28_pii_scanner_exact_cases() -> None:
    # 1. 4111 1111 1111 1111 is flagged card_number (passes Luhn)
    assert luhn_check("4111111111111111") is True
    assert scan_pii("4111 1111 1111 1111") == "card_number"

    # 2. 4111 1111 1111 1112 fails Luhn and is flagged long_number (16 digits)
    assert luhn_check("4111111111111112") is False
    assert scan_pii("4111 1111 1111 1112") == "long_number"

    # 3. 1234 5678 9012 is flagged long_number
    assert scan_pii("1234 5678 9012") == "long_number"

    # 4. +91 98765 43210 is flagged phone
    assert scan_pii("+91 98765 43210") == "phone"

    # 5. a.b@campus.edu is flagged email
    assert scan_pii("Contact me at a.b@campus.edu please") == "email"

    # 6. blue bottle with a RIA sticker is not flagged
    assert scan_pii("blue bottle with a RIA sticker") is None


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
    loc = CampusLocation(name="Student Center", kind="building")
    db_session.add(loc)
    await db_session.commit()
    return loc.id


@pytest.mark.asyncio
async def test_ac_29_public_fields_with_pii_rejected_without_echoing_value(
    async_client: AsyncClient, user_auth: dict[str, str], sample_location: uuid.UUID
) -> None:
    headers = {"X-CSRF-Token": user_auth["csrf_token"]}
    cookies = {"session_id": user_auth["session_id"]}

    secret_phone = "+91 98765 43210"

    # 1. Public title containing phone is rejected with 422 pii_detected
    res_title_pii = await async_client.post(
        "/api/reports/lost",
        json={
            "title": f"Call me at {secret_phone}",
            "description": "Lost my keys in classroom 101",
            "category": "keys",
            "location_id": str(sample_location),
            "date": str(date.today()),
            "time_precision": "morning",
        },
        headers=headers,
        cookies=cookies,
    )
    assert res_title_pii.status_code == 422
    data = res_title_pii.json()
    assert data["detail"]["code"] == "pii_detected"
    assert data["detail"]["kind"] == "phone"
    # Never echo the sensitive value per AC-29!
    assert secret_phone not in str(data)

    # 2. Public description containing card number is rejected with 422 pii_detected
    secret_card = "4111 1111 1111 1111"
    res_desc_pii = await async_client.post(
        "/api/reports/lost",
        json={
            "title": "Lost debit card",
            "description": f"The card number is {secret_card}",
            "category": "wallet",
            "location_id": str(sample_location),
            "date": str(date.today()),
            "time_precision": "day",
        },
        headers=headers,
        cookies=cookies,
    )
    assert res_desc_pii.status_code == 422
    data_card = res_desc_pii.json()
    assert data_card["detail"]["code"] == "pii_detected"
    assert data_card["detail"]["kind"] == "card_number"
    assert secret_card not in str(data_card)

    # 3. Private details may contain such text and show warning / succeed (AC-29)
    res_private_ok = await async_client.post(
        "/api/reports/found",
        json={
            "title": "Found phone near canteen",
            "description": "Black smartphone with cracked screen protector",
            "category": "phone",
            "location_id": str(sample_location),
            "date": str(date.today()),
            "time_precision": "afternoon",
            "private_details": f"Locked screen shows emergency contact: {secret_phone}",
            "verification_prompts": ["What is the wallpaper?"],
        },
        headers=headers,
        cookies=cookies,
    )
    assert res_private_ok.status_code == 201
