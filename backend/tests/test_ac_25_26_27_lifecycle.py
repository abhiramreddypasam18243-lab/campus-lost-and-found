from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.domain.lifecycle import (
    ALL_FOUND_ACTIONS,
    ALL_FOUND_STATES,
    ALL_LOST_ACTIONS,
    ALL_LOST_STATES,
    FOUND_TRANSITIONS,
    LOST_TRANSITIONS,
    transition_found_report,
    transition_lost_report,
)
from app.models.location import CampusLocation
from app.models.user import User


def test_ac_25_exhaustive_found_report_lifecycle() -> None:
    """AC-25: Every legal transition in 5.1 succeeds; every other pair raises ValueError."""
    for state in ALL_FOUND_STATES:
        for action in ALL_FOUND_ACTIONS:
            pair = (state, action)
            if pair in FOUND_TRANSITIONS:
                expected_next = FOUND_TRANSITIONS[pair]
                assert transition_found_report(state, action) == expected_next
            else:
                with pytest.raises(ValueError, match="invalid_transition"):
                    transition_found_report(state, action)


def test_ac_26_exhaustive_lost_report_lifecycle() -> None:
    """AC-26: Exhaustive check for lost-report lifecycle."""
    for state in ALL_LOST_STATES:
        for action in ALL_LOST_ACTIONS:
            pair = (state, action)
            if pair in LOST_TRANSITIONS:
                expected_next = LOST_TRANSITIONS[pair]
                assert transition_lost_report(state, action) == expected_next
            else:
                with pytest.raises(ValueError, match="invalid_transition"):
                    transition_lost_report(state, action)


@pytest.mark.asyncio
async def test_ac_27_close_own_report_and_foreign_returns_404(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    # 1. Create two users: Student A and Student B
    user_a = User(
        email="student_a@campus.edu",
        password_hash=hash_password("password_user_a123!"),
        role="user",
        email_verified_at=pytest.importorskip("datetime").datetime.now(
            pytest.importorskip("datetime").UTC
        ),
    )
    user_b = User(
        email="student_b@campus.edu",
        password_hash=hash_password("password_user_b123!"),
        role="user",
        email_verified_at=pytest.importorskip("datetime").datetime.now(
            pytest.importorskip("datetime").UTC
        ),
    )
    loc = CampusLocation(name="North Block", kind="building")
    db_session.add_all([user_a, user_b, loc])
    await db_session.commit()

    # Login User A
    login_a = await async_client.post(
        "/api/auth/login",
        json={"email": "student_a@campus.edu", "password": "password_user_a123!"},
    )
    csrf_a = login_a.headers.get("X-CSRF-Token") or login_a.json()["csrf_token"]
    cookie_a = login_a.cookies.get("session_id", "")

    # User A creates a lost report
    create_res = await async_client.post(
        "/api/reports/lost",
        json={
            "title": "Lost Wallet",
            "description": "Black leather wallet left on table in cafeteria",
            "category": "wallet",
            "location_id": str(loc.id),
            "date": str(date.today()),
            "time_precision": "afternoon",
        },
        headers={"X-CSRF-Token": csrf_a},
        cookies={"session_id": cookie_a},
    )
    assert create_res.status_code == 201
    report_id = create_res.json()["id"]

    # Login User B
    login_b = await async_client.post(
        "/api/auth/login",
        json={"email": "student_b@campus.edu", "password": "password_user_b123!"},
    )
    csrf_b = login_b.headers.get("X-CSRF-Token") or login_b.json()["csrf_token"]
    cookie_b = login_b.cookies.get("session_id", "")

    # User B tries to close User A's report -> returns 404 (anti-enumeration per AC-27)
    res_b_close = await async_client.patch(
        f"/api/reports/{report_id}/close",
        headers={"X-CSRF-Token": csrf_b},
        cookies={"session_id": cookie_b},
    )
    assert res_b_close.status_code == 404

    # User A closes their own report -> succeeds (200)
    res_a_close = await async_client.patch(
        f"/api/reports/{report_id}/close",
        headers={"X-CSRF-Token": csrf_a},
        cookies={"session_id": cookie_a},
    )
    assert res_a_close.status_code == 200
    assert res_a_close.json()["status"] == "closed"


def test_ac_27_returned_found_report_can_never_reopen() -> None:
    # A returned found report has no legal outgoing transitions
    for action in ALL_FOUND_ACTIONS:
        with pytest.raises(ValueError, match="invalid_transition"):
            transition_found_report("returned", action)
