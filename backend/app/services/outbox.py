"""Notification email delivery from the outbox (AC-68 to AC-73).

Notification rows are written in the same transaction as the state change that causes them.
The worker later claims pending rows with FOR UPDATE SKIP LOCKED, renders the whitelisted
template and sends it with the row's fixed Message-ID, so a retry after a crash is
recognisable as a duplicate (AC-69). In-app visibility does not depend on this status.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.notifications import Notification
from app.models.user import User
from app.services.mailer import send_email
from app.services.notification import (
    handle_notification_smtp_failure,
    render_notification_content,
)

logger = logging.getLogger("worker")


async def deliver_pending_emails(
    session_factory: async_sessionmaker[AsyncSession], batch_size: int = 20
) -> int:
    """Send due notification emails; returns the number of rows handled."""
    now = datetime.now(UTC)
    async with session_factory() as db:
        stmt = (
            select(Notification)
            .where(Notification.status == "pending", Notification.run_after <= now)
            .order_by(Notification.created_at.asc())
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        rows = list((await db.execute(stmt)).scalars().all())
        for notif in rows:
            if not notif.email_queued:
                # Opted out or over the daily cap (AC-72, AC-73): in-app only.
                notif.status = "in_app_only"
                continue
            user = await db.get(User, notif.user_id)
            if user is None or user.status != "active":
                notif.status = "in_app_only"
                continue
            subject, body = render_notification_content(notif.event_type, notif.payload)
            try:
                await send_email(user.email, subject, body, notif.message_id)
            except Exception as exc:
                handle_notification_smtp_failure(notif, type(exc).__name__)
                logger.warning("notification email %s failed: %s", notif.id, type(exc).__name__)
                continue
            notif.status = "sent"
            notif.attempts += 1
        await db.commit()
    return len(rows)
