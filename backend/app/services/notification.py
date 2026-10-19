import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notifications import Notification
from app.models.user import User

BACKOFF_MINUTES = [1, 2, 4, 8]


def utc_now() -> datetime:
    return datetime.now(UTC)


def render_notification_content(event_type: str, payload: dict[str, Any]) -> tuple[str, str]:
    """Whitelisted template rendering guaranteeing no private fields or evidence leaks (AC-71)."""
    if event_type == "match_suggested":
        category = payload.get("category", "item")
        title = payload.get("title", "item")
        subject = f"Potential match found: {category}"
        body = f"A potential match has been suggested for '{title}'. Visit the portal to view the suggestion."
        return subject, body

    if event_type == "claim_update":
        found_title = payload.get("found_title", "item")
        claim_status = payload.get("claim_status", "reviewed")
        subject = f"Claim update: {found_title}"
        body = f"Your claim for '{found_title}' has been updated to: {claim_status}."
        return subject, body

    if event_type == "handover_ready":
        found_title = payload.get("found_title", "item")
        is_claimant = bool(payload.get("is_claimant", False))
        handover_code = payload.get("handover_code", "")

        subject = f"Handover ready: {found_title}"
        if is_claimant:
            body = (
                f"Your claim for '{found_title}' was approved! "
                f"Your single-use handover verification code is: {handover_code}. "
                "Present this code at the campus lost-and-found desk."
            )
        else:
            body = f"A handover has been scheduled for the found item '{found_title}'."
        return subject, body

    return (
        f"Notification: {event_type}",
        "You have an update on the Smart Campus Lost and Found portal.",
    )


async def create_notification(
    db: AsyncSession,
    user_id: uuid.UUID,
    event_type: str,
    event_key: str,
    payload: dict[str, Any],
) -> Notification:
    """Create a notification in the ongoing database transaction (outbox pattern per AC-68, AC-69)."""
    # AC-69: Deduplicate by event_key
    stmt = select(Notification).where(Notification.event_key == event_key)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return existing

    # Check user email preferences (AC-72) and daily limit (AC-73)
    user_stmt = select(User).where(User.id == user_id)
    user = (await db.execute(user_stmt)).scalar_one()

    email_queued = True
    if event_type == "match_suggested":
        # AC-72: Match email opt-out check
        if not user.notify_match_email:
            email_queued = False
        else:
            # AC-73: At most 5 match emails per user per day
            cutoff = utc_now() - timedelta(days=1)
            count_stmt = (
                select(func.count())
                .select_from(Notification)
                .where(
                    Notification.user_id == user_id,
                    Notification.event_type == "match_suggested",
                    Notification.email_queued.is_(True),
                    Notification.created_at >= cutoff,
                )
            )
            match_count = (await db.execute(count_stmt)).scalar_one()
            if match_count >= 5:
                email_queued = False

    # AC-69: Deterministic Message-ID
    message_id = f"<{event_key}@campus.edu>"

    notif = Notification(
        user_id=user_id,
        event_type=event_type,
        event_key=event_key,
        payload=payload,
        email_queued=email_queued,
        status="pending",
        attempts=0,
        run_after=utc_now(),
        message_id=message_id,
    )
    db.add(notif)
    await db.flush()
    return notif


def handle_notification_smtp_failure(
    notif: Notification, error_msg: str, current_time: datetime | None = None
) -> None:
    """Apply exponential backoff (1, 2, 4, 8 min) or fail after 5 attempts (AC-70)."""
    now = current_time or utc_now()
    notif.attempts += 1
    notif.last_error = error_msg

    if notif.attempts < 5:
        notif.status = "pending"
        backoff_idx = min(notif.attempts - 1, len(BACKOFF_MINUTES) - 1)
        notif.run_after = now + timedelta(minutes=BACKOFF_MINUTES[backoff_idx])
    else:
        notif.status = "failed"
