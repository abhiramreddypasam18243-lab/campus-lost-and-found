import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notifications import Notification
from app.models.user import User
from app.services.notification import (
    create_notification,
    handle_notification_smtp_failure,
)


@pytest.fixture
async def sample_user(db_session: AsyncSession) -> User:
    user = User(
        email="notify_user@campus.edu",
        password_hash="any_hash",
        role="user",
        email_verified_at=datetime.now(UTC),
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_ac_68_notification_transactional_rollback(
    db_session: AsyncSession, sample_user: User
) -> None:
    """AC-68: Notification is written in the same transaction; rolls back atomically."""
    event_key = f"evt_test_rollback_{uuid.uuid4()}"

    try:
        async with db_session.begin_nested():
            await create_notification(
                db=db_session,
                user_id=sample_user.id,
                event_type="test_event",
                event_key=event_key,
                payload={"msg": "Hello"},
            )
            # Simulate failure that triggers rollback
            raise ValueError("Forced error to trigger rollback")
    except ValueError:
        pass

    # Verify notification does not exist in DB
    stmt = select(Notification).where(Notification.event_key == event_key)
    row = (await db_session.execute(stmt)).scalar_one_or_none()
    assert row is None


@pytest.mark.asyncio
async def test_ac_69_unique_event_key_and_consistent_message_id(
    db_session: AsyncSession, sample_user: User
) -> None:
    """AC-69: Processing the same event twice creates one notification; retried email carries same Message-ID."""
    event_key = f"evt_match_{uuid.uuid4()}"

    # First event processing
    n1 = await create_notification(
        db=db_session,
        user_id=sample_user.id,
        event_type="match_suggested",
        event_key=event_key,
        payload={"match_id": str(uuid.uuid4())},
    )
    await db_session.commit()

    # Second event processing with identical event_key
    n2 = await create_notification(
        db=db_session,
        user_id=sample_user.id,
        event_type="match_suggested",
        event_key=event_key,
        payload={"match_id": str(uuid.uuid4())},
    )
    await db_session.commit()

    # Verify only 1 notification exists in DB
    stmt = select(func.count()).select_from(Notification).where(Notification.event_key == event_key)
    count = (await db_session.execute(stmt)).scalar_one()
    assert count == 1
    assert n1.id == n2.id

    # Verify deterministic Message-ID
    assert n1.message_id is not None
    assert event_key in n1.message_id
    assert n1.message_id == n2.message_id


@pytest.mark.asyncio
async def test_ac_70_smtp_failure_retry_and_failed_state(
    db_session: AsyncSession, sample_user: User
) -> None:
    """AC-70: SMTP failure retried with exponential backoff up to 5 attempts, then marked failed."""
    event_key = f"evt_smtp_{uuid.uuid4()}"
    notif = await create_notification(
        db=db_session,
        user_id=sample_user.id,
        event_type="match_suggested",
        event_key=event_key,
        payload={"title": "Lost Wallet"},
    )
    await db_session.commit()

    base_time = datetime(2026, 10, 19, 14, 0, 0, tzinfo=UTC)
    curr_time = base_time
    expected_backoffs = [1, 2, 4, 8]

    for minutes in expected_backoffs:
        handle_notification_smtp_failure(
            notif, error_msg="SMTP connection refused", current_time=curr_time
        )
        await db_session.commit()
        await db_session.refresh(notif)

        assert notif.status == "pending"
        expected_run_after = curr_time + timedelta(minutes=minutes)
        assert notif.run_after == expected_run_after
        curr_time = expected_run_after

    # 5th attempt fails -> marked failed
    handle_notification_smtp_failure(
        notif, error_msg="Permanent SMTP failure", current_time=curr_time
    )
    await db_session.commit()
    await db_session.refresh(notif)

    assert notif.attempts == 5
    assert notif.status == "failed"
    assert notif.last_error == "Permanent SMTP failure"
