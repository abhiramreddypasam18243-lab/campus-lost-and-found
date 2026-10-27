"""SMTP delivery (D8): Mailpit in development, the configured SMTP server in production.

Only rendered, whitelisted text is sent (AC-71). Logs never contain addresses, tokens or codes
(SEC12): a failure records the exception type only.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage
from urllib.parse import quote

from app.core.config import get_settings

logger = logging.getLogger("mailer")


def _send_sync(to_address: str, subject: str, body: str, message_id: str | None) -> None:
    settings = get_settings()
    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to_address
    msg["Subject"] = subject
    if message_id:
        msg["Message-ID"] = message_id  # AC-69: the same ID on every retry
    msg.set_content(body)
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
        if settings.SMTP_USE_TLS:
            smtp.starttls()
        if settings.SMTP_USER and settings.SMTP_PASSWORD:
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(msg)


async def send_email(
    to_address: str, subject: str, body: str, message_id: str | None = None
) -> None:
    """Send one email without blocking the event loop. Raises on SMTP failure."""
    await asyncio.to_thread(_send_sync, to_address, subject, body, message_id)


async def send_verification_email(
    to_address: str, raw_token: str, raw_code: str | None = None
) -> bool:
    """AC-02: email the single-use verification code and link. Returns False if delivery failed."""
    settings = get_settings()
    link = f"{settings.APP_BASE_URL.rstrip('/')}/#/verify?token={quote(raw_token)}"
    code_block = (
        f"\nYour 6-digit verification code is:\n  {raw_code}\n\nEnter this code on the website to activate your account.\n"
        if raw_code
        else ""
    )
    body = (
        "Welcome to the Campus Lost and Found network.\n\n"
        f"{code_block}\n"
        f"You can also confirm your campus email address by opening this link:\n{link}\n\n"
        "The code and link work once and expire in 24 hours. If you did not register, ignore this email."
    )
    subject = f"Your verification code: {raw_code}" if raw_code else "Confirm your campus email"
    try:
        await send_email(to_address, subject, body)
    except Exception as exc:
        logger.warning("verification email not sent: %s", type(exc).__name__)
        return False
    return True
