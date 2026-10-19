import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.notification import create_notification


@pytest.fixture
async def setup_users(db_session: AsyncSession) -> dict[str, User]:
    # User opted out of match emails
    opted_out = User(
        email="opted_out@campus.edu",
        password_hash="any_hash",
        role="user",
        notify_match_email=False,
        email_verified_at=datetime.now(UTC),
    )
    # User opted in
    opted_in = User(
        email="opted_in@campus.edu",
        password_hash="any_hash",
        role="user",
        notify_match_email=True,
        email_verified_at=datetime.now(UTC),
    )
    db_session.add_all([opted_out, opted_in])
    await db_session.commit()
    return {"opted_out": opted_out, "opted_in": opted_in}


@pytest.mark.asyncio
async def test_ac_72_email_opt_out_preferences(
    db_session: AsyncSession, setup_users: dict[str, User]
) -> None:
    """AC-72: Opting out of match emails stops them but not claim/handover emails; in-app still appears."""
    user = setup_users["opted_out"]

    # 1. Match event for opted-out user: in-app created, email skipped
    n_match = await create_notification(
        db=db_session,
        user_id=user.id,
        event_type="match_suggested",
        event_key=f"evt_match_{uuid.uuid4()}",
        payload={"title": "Lost Wallet"},
    )
    await db_session.commit()

    assert n_match is not None
    assert n_match.email_queued is False  # Email suppressed!

    # 2. Claim update for opted-out user: email IS queued
    n_claim = await create_notification(
        db=db_session,
        user_id=user.id,
        event_type="claim_update",
        event_key=f"evt_claim_{uuid.uuid4()}",
        payload={"title": "Lost Wallet", "status": "approved"},
    )
    await db_session.commit()

    assert n_claim.email_queued is True

    # 3. Handover event for opted-out user: email IS queued
    n_handover = await create_notification(
        db=db_session,
        user_id=user.id,
        event_type="handover_ready",
        event_key=f"evt_handover_{uuid.uuid4()}",
        payload={"title": "Lost Wallet", "code": "ABCD-1234"},
    )
    await db_session.commit()

    assert n_handover.email_queued is True


@pytest.mark.asyncio
async def test_ac_73_daily_match_email_rate_cap(
    db_session: AsyncSession, setup_users: dict[str, User]
) -> None:
    """AC-73: At most 5 match emails per user per day; 6th appears in-app only."""
    user = setup_users["opted_in"]

    # Send 5 match notifications
    for i in range(5):
        n = await create_notification(
            db=db_session,
            user_id=user.id,
            event_type="match_suggested",
            event_key=f"evt_cap_{i}_{uuid.uuid4()}",
            payload={"match_id": str(uuid.uuid4())},
        )
        await db_session.commit()
        assert n.email_queued is True, f"Notification {i + 1} should have queued an email"

    # 6th match notification on same day
    n_6 = await create_notification(
        db=db_session,
        user_id=user.id,
        event_type="match_suggested",
        event_key=f"evt_cap_6_{uuid.uuid4()}",
        payload={"match_id": str(uuid.uuid4())},
    )
    await db_session.commit()

    # In-app notification created, but email is NOT queued
    assert n_6 is not None
    assert n_6.email_queued is False
