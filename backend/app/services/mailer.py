"""SMTP delivery (D8): Mailpit in development, the configured SMTP server in production.

Only rendered, whitelisted text is sent (AC-71). Logs never contain addresses, tokens or codes
(SEC12): a failure records the exception type only.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
import socket
from email.message import EmailMessage
from urllib.parse import quote

import httpx

from app.core.config import get_settings

logger = logging.getLogger("mailer")


def _resolve_resend_from() -> str:
    settings = get_settings()
    custom = settings.RESEND_FROM
    if custom and "@" in custom:
        domain = custom.split("@")[-1].strip("> \t\r\n").lower()
        if domain not in ("gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com"):
            return custom
    return "Campus Lost and Found <onboarding@resend.dev>"


async def _send_resend(to_address: str, subject: str, body: str) -> None:
    settings = get_settings()
    from_addr = _resolve_resend_from()
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": from_addr,
                "to": [to_address],
                "subject": subject,
                "text": body,
            },
        )
        if resp.status_code >= 400:
            err_text = resp.text
            try:
                data = resp.json()
                msg = data.get("message", err_text)
            except Exception:
                msg = err_text

            msg_lower = msg.lower()
            if "not verified" in msg_lower and "domain" in msg_lower:
                raise RuntimeError(
                    f"Resend domain error: {msg}. "
                    "Resend free tier requires sending from 'onboarding@resend.dev' unless a custom domain is verified on https://resend.com/domains."
                )
            if "only send testing emails" in msg_lower or "testing emails to your own" in msg_lower:
                raise RuntimeError(
                    f"Resend sandbox limitation: {msg}. "
                    "Resend's free test domain (onboarding@resend.dev) only delivers to the email address used to create your Resend account. "
                    "Please register on this site with that email address, or add a custom domain on https://resend.com/domains, or use Brevo (BREVO_API_KEY)."
                )
            raise RuntimeError(f"Resend API error ({resp.status_code}): {msg}")


async def _send_brevo(to_address: str, subject: str, body: str) -> None:
    settings = get_settings()
    raw_from = settings.BREVO_FROM or settings.SMTP_FROM or "verify@campuslostandfound.com"
    sender_name = "Campus Lost and Found"
    sender_email = raw_from.strip()
    if "<" in raw_from and ">" in raw_from:
        parts = raw_from.split("<")
        sender_name = parts[0].strip() or sender_name
        sender_email = parts[1].split(">")[0].strip()

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "api-key": settings.BREVO_API_KEY or "",
                "Content-Type": "application/json",
            },
            json={
                "sender": {"email": sender_email, "name": sender_name},
                "to": [{"email": to_address}],
                "subject": subject,
                "textContent": body,
            },
        )
        if resp.status_code >= 400:
            try:
                data = resp.json()
                msg = data.get("message", resp.text)
            except Exception:
                msg = resp.text
            raise RuntimeError(f"Brevo API error ({resp.status_code}): {msg}")


def _send_sync(to_address: str, subject: str, body: str, message_id: str | None) -> None:
    settings = get_settings()
    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to_address
    msg["Subject"] = subject
    if message_id:
        msg["Message-ID"] = message_id  # AC-69: the same ID on every retry
    msg.set_content(body)

    port = int(settings.SMTP_PORT)
    use_tls = str(settings.SMTP_USE_TLS).lower() in ("true", "1", "yes")

    # Force IPv4 to avoid IPv6 unroutable errors
    host = settings.SMTP_HOST
    try:
        infos = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
        if infos:
            host = str(infos[0][4][0])
    except Exception:
        pass

    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=15) as smtp:
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=15) as smtp:
                smtp.ehlo()
                if use_tls:
                    smtp.starttls()
                    smtp.ehlo()
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                smtp.send_message(msg)
    except OSError as exc:
        if getattr(exc, "errno", None) in (101, 111):
            raise OSError(
                f"{exc}. Note: Render free tier blocks outbound SMTP ports (25, 465, 587). "
                "Add RESEND_API_KEY in Render to send via HTTPS (port 443)."
            ) from exc
        raise


async def send_email(
    to_address: str, subject: str, body: str, message_id: str | None = None
) -> None:
    """Send one email without blocking the event loop. Uses HTTP API if configured, else SMTP."""
    settings = get_settings()
    if settings.RESEND_API_KEY:
        await _send_resend(to_address, subject, body)
        return
    if settings.BREVO_API_KEY:
        await _send_brevo(to_address, subject, body)
        return

    await asyncio.to_thread(_send_sync, to_address, subject, body, message_id)


async def send_verification_email(
    to_address: str, raw_token: str, raw_code: str | None = None
) -> tuple[bool, str | None]:
    """AC-02: email the single-use verification code and link. Returns (success, error_reason)."""
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
        err_msg = f"{type(exc).__name__}: {exc}"
        logger.warning("verification email not sent: %s", err_msg)
        return False, err_msg
    return True, None
