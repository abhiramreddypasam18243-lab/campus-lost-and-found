import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.notifications import Notification
from app.models.user import User


@pytest.fixture
async def users_with_notifications(
    db_session: AsyncSession, async_client: AsyncClient
) -> dict[str, any]:
    user_a = User(
        email="user_a_notif@campus.edu",
        password_hash=hash_password("Pass1234!"),
        role="user",
        email_verified_at=datetime.now(UTC),
    )
    user_b = User(
        email="user_b_notif@campus.edu",
        password_hash=hash_password("Pass1234!"),
        role="user",
        email_verified_at=datetime.now(UTC),
    )
    db_session.add_all([user_a, user_b])
    await db_session.commit()

    async def login(email: str) -> dict[str, str]:
        res = await async_client.post(
            "/api/auth/login",
            json={"email": email, "password": "Pass1234!"},
        )
        return {
            "cookies": {"session_id": res.cookies.get("session_id", "")},
            "csrf_token": res.headers.get("X-CSRF-Token") or res.json()["csrf_token"],
        }

    # Seed 3 notifications for User A: 2 unread, 1 read
    n1 = Notification(
        user_id=user_a.id,
        event_type="match_suggested",
        event_key=f"evt_1_{uuid.uuid4()}",
        payload={"title": "Unread 1"},
        status="sent",
        read_at=None,
    )
    n2 = Notification(
        user_id=user_a.id,
        event_type="claim_update",
        event_key=f"evt_2_{uuid.uuid4()}",
        payload={"title": "Unread 2"},
        status="sent",
        read_at=None,
    )
    n3 = Notification(
        user_id=user_a.id,
        event_type="handover_ready",
        event_key=f"evt_3_{uuid.uuid4()}",
        payload={"title": "Read 3"},
        status="sent",
        read_at=datetime.now(UTC),
    )
    db_session.add_all([n1, n2, n3])
    await db_session.commit()

    return {
        "user_a": user_a,
        "user_b": user_b,
        "n1": n1,
        "n2": n2,
        "n3": n3,
        "auth_a": await login("user_a_notif@campus.edu"),
        "auth_b": await login("user_b_notif@campus.edu"),
    }


@pytest.mark.asyncio
async def test_ac_74_in_app_notifications_owner_filtering_and_read(
    async_client: AsyncClient, users_with_notifications: dict[str, any]
) -> None:
    """AC-74: In-app notifications are owner-only, paginated, and support read and unread."""
    auth_a = users_with_notifications["auth_a"]
    auth_b = users_with_notifications["auth_b"]
    n1 = users_with_notifications["n1"]
    n3 = users_with_notifications["n3"]

    # 1. User B sees 0 notifications (owner-only)
    res_b = await async_client.get("/api/notifications", cookies=auth_b["cookies"])
    assert res_b.status_code == 200
    assert len(res_b.json()["items"]) == 0

    # 2. User A sees all 3 notifications
    res_a_all = await async_client.get("/api/notifications", cookies=auth_a["cookies"])
    assert res_a_all.status_code == 200
    assert len(res_a_all.json()["items"]) == 3

    # 3. Filter unread (status=unread) -> returns 2 items
    res_unread = await async_client.get(
        "/api/notifications?status=unread", cookies=auth_a["cookies"]
    )
    assert res_unread.status_code == 200
    unread_items = res_unread.json()["items"]
    assert len(unread_items) == 2
    assert all(item["read_at"] is None for item in unread_items)

    # 4. Filter read (status=read) -> returns 1 item
    res_read = await async_client.get("/api/notifications?status=read", cookies=auth_a["cookies"])
    assert res_read.status_code == 200
    read_items = res_read.json()["items"]
    assert len(read_items) == 1
    assert read_items[0]["id"] == str(n3.id)

    # 5. User B tries to mark User A's notification as read -> returns 404 (anti-enumeration)
    res_foreign_read = await async_client.post(
        f"/api/notifications/{n1.id}/read",
        cookies=auth_b["cookies"],
        headers={"X-CSRF-Token": auth_b["csrf_token"]},
    )
    assert res_foreign_read.status_code == 404

    # 6. User A marks unread n1 as read -> 200 OK
    res_mark_read = await async_client.post(
        f"/api/notifications/{n1.id}/read",
        cookies=auth_a["cookies"],
        headers={"X-CSRF-Token": auth_a["csrf_token"]},
    )
    assert res_mark_read.status_code == 200
    assert res_mark_read.json()["read_at"] is not None

    # Verify unread count is now 1
    res_unread_now = await async_client.get(
        "/api/notifications?status=unread", cookies=auth_a["cookies"]
    )
    assert len(res_unread_now.json()["items"]) == 1
