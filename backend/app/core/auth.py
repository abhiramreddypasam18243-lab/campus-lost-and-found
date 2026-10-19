from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import hash_token
from app.models.user import Session, User

SESSION_COOKIE_NAME = "session_id"


def utc_now() -> datetime:
    return datetime.now(UTC)


async def get_current_session_and_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> tuple[Session, User] | None:
    """Resolve active session and user from session cookie."""
    if not session_id:
        return None

    token_hash = hash_token(session_id)
    now = utc_now()

    stmt = (
        select(Session)
        .options(selectinload(Session.user))
        .where(
            Session.token_hash == token_hash,
            Session.revoked_at.is_(None),
            Session.expires_at > now,
        )
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if not session or not session.user or session.user.status != "active":
        return None

    return session, session.user


async def get_current_user_optional(
    session_data: tuple[Session, User] | None = Depends(get_current_session_and_user),
) -> User | None:
    """Return user if authenticated, otherwise None."""
    return session_data[1] if session_data else None


async def require_authenticated_user(
    session_data: tuple[Session, User] | None = Depends(get_current_session_and_user),
) -> User:
    """AC-05: Require a valid session; returns 401 if missing, expired, or revoked."""
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Authentication required."},
        )
    return session_data[1]


async def require_verified_user(
    user: User = Depends(require_authenticated_user),
) -> User:
    """AC-02: Require that the user's campus email has been verified."""
    if not user.email_verified_at:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "email_not_verified", "message": "Campus email verification required."},
        )
    return user


def require_role(*allowed_roles: str) -> Callable[..., Any]:
    """AC-08 (SEC4): Enforce role-based access control based on session role."""
    async def role_checker(user: User = Depends(require_authenticated_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "forbidden", "message": f"Requires one of: {allowed_roles}"},
            )
        return user
    return role_checker


async def verify_csrf(
    request: Request,
    session_data: tuple[Session, User] | None = Depends(get_current_session_and_user),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> None:
    """AC-06 (SEC3): Enforce CSRF token verification on state-changing requests."""
    # Safe methods do not require CSRF token
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return

    # If user is authenticated, CSRF token is mandatory
    if session_data:
        session, _ = session_data
        if not x_csrf_token or hash_token(x_csrf_token) != session.csrf_token_hash:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "csrf_failed", "message": "Missing or invalid CSRF token."},
            )
