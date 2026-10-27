import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    SESSION_COOKIE_NAME,
    get_current_session_and_user,
    require_authenticated_user,
    utc_now,
    verify_csrf,
)
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import (
    check_tls_requirement,
    generate_secure_token,
    hash_password,
    hash_token,
    login_rate_limiter,
    request_is_tls,
    verify_dummy_password,
    verify_password,
)
from app.models.user import EmailToken, Session, User
from app.schemas.auth import (
    CsrfResponse,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationResponse,
    UpdateMeRequest,
    UserResponse,
    VerifyEmailRequest,
)
from app.services.audit import write_audit_log
from app.services.mailer import send_verification_email

router = APIRouter(prefix="/api", tags=["auth"])
settings = get_settings()


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        email_verified=user.email_verified_at is not None,
        notify_match_email=user.notify_match_email,
        created_at=user.created_at,
    )


@router.post("/auth/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    req: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    """AC-01: Register user with an email in ALLOWED_EMAIL_DOMAINS (exact domain match)."""
    email_clean = req.email.strip().lower()
    domain = email_clean.split("@")[-1]

    # Validate campus email domain (P5: exact match against the configured whitelist)
    if domain not in settings.ALLOWED_EMAIL_DOMAINS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "email_domain_not_allowed",
                "message": f"Domain '@{domain}' is not allowed.",
            },
        )

    # Check for existing email (case-insensitive)
    stmt = select(User).where(func.lower(User.email) == email_clean)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "email_already_registered", "message": "Email is already registered."},
        )

    # Create unverified user with Argon2id hash
    pwd_hash = hash_password(req.password)
    new_user = User(
        email=email_clean,
        password_hash=pwd_hash,
        display_name=req.display_name,
        role="user",
        email_verified_at=None,
        status="active",
    )
    db.add(new_user)
    await db.flush()

    # Create verification token & 6-digit code (expires in 24 hours per AC-02)
    raw_token = generate_secure_token()
    raw_code = f"{secrets.randbelow(900000) + 100000}"
    expires_at = utc_now() + timedelta(hours=24)
    token_entry = EmailToken(
        user_id=new_user.id,
        token_hash=hash_token(raw_token),
        purpose="verify_email",
        expires_at=expires_at,
    )
    code_entry = EmailToken(
        user_id=new_user.id,
        token_hash=hash_token(raw_code),
        purpose="verify_email",
        expires_at=expires_at,
    )
    db.add(token_entry)
    db.add(code_entry)

    await write_audit_log(
        db=db,
        actor_id=new_user.id,
        role="user",
        action="user_registered",
        entity_type="user",
        entity_id=new_user.id,
        summary={"email": email_clean},
    )
    await db.commit()

    # Sent after commit so a mail outage never loses the account; a failure is logged
    # (never the token or the address) and registration still succeeds.
    await send_verification_email(email_clean, raw_token, raw_code)

    return RegisterResponse(
        message="Account created. Verification code sent to your email.",
        email=email_clean,
    )


@router.post("/auth/resend-verification", response_model=ResendVerificationResponse)
async def resend_verification(
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> ResendVerificationResponse:
    """AC-02: Resend email verification code for the currently logged-in user."""
    if current_user.email_verified_at is not None:
        return ResendVerificationResponse(message="Email is already verified.")

    raw_token = generate_secure_token()
    raw_code = f"{secrets.randbelow(900000) + 100000}"
    expires_at = utc_now() + timedelta(hours=24)
    token_entry = EmailToken(
        user_id=current_user.id,
        token_hash=hash_token(raw_token),
        purpose="verify_email",
        expires_at=expires_at,
    )
    code_entry = EmailToken(
        user_id=current_user.id,
        token_hash=hash_token(raw_code),
        purpose="verify_email",
        expires_at=expires_at,
    )
    db.add(token_entry)
    db.add(code_entry)
    await db.commit()

    sent, err_msg = await send_verification_email(current_user.email, raw_token, raw_code)
    if not sent:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "email_delivery_failed",
                "message": f"Could not deliver email ({err_msg}). Please check SMTP settings in Render.",
            },
        )

    return ResendVerificationResponse(
        message="Verification code sent to your email.",
    )


@router.post("/auth/verify-email")
async def verify_email(
    req: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """AC-02: Verify email using single-use 6-digit code or link token."""
    submitted = (req.code or req.token or "").strip()
    if not submitted:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "missing_code", "message": "Verification code is required."},
        )

    token_hash = hash_token(submitted)
    now = utc_now()

    stmt = select(EmailToken).where(
        EmailToken.token_hash == token_hash,
        EmailToken.purpose == "verify_email",
    )
    token_entry = (await db.execute(stmt)).scalar_one_or_none()

    # Reused or expired code/token returns 410 per AC-02
    if not token_entry or token_entry.used_at is not None or token_entry.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={
                "code": "token_expired_or_invalid",
                "message": "Verification code has expired or been used.",
            },
        )

    # Mark all active verification tokens for this user as used
    token_entry.used_at = now
    stmt_tokens = select(EmailToken).where(
        EmailToken.user_id == token_entry.user_id,
        EmailToken.purpose == "verify_email",
        EmailToken.used_at.is_(None),
    )
    all_user_tokens = (await db.execute(stmt_tokens)).scalars().all()
    for t in all_user_tokens:
        t.used_at = now

    stmt_user = select(User).where(User.id == token_entry.user_id)
    user = (await db.execute(stmt_user)).scalar_one()
    user.email_verified_at = now

    await write_audit_log(
        db=db,
        actor_id=user.id,
        role=user.role,
        action="email_verified",
        entity_type="user",
        entity_id=user.id,
    )
    await db.commit()

    return {"message": "Email verified successfully."}


@router.post("/auth/login", response_model=LoginResponse)
async def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """AC-04, AC-07, SEC2, SEC5, SEC6: Authenticate user, rate limit, issue session cookie & CSRF token."""
    check_tls_requirement(request)

    email_clean = req.email.strip().lower()
    client_ip = request.client.host if request.client else "unknown"

    # Rate limiting (SEC6, AC-04)
    for key in (email_clean, client_ip):
        is_limited, retry_after = login_rate_limiter.is_rate_limited(key)
        if is_limited:
            response.headers["Retry-After"] = str(retry_after)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"code": "too_many_attempts", "message": "Too many failed login attempts."},
                headers={"Retry-After": str(retry_after)},
            )

    # SEC5: Check user with identical error response and dummy password timing protection
    stmt = select(User).where(User.email == email_clean)
    user = (await db.execute(stmt)).scalar_one_or_none()

    if not user:
        verify_dummy_password()
        login_rate_limiter.record_failure(email_clean)
        login_rate_limiter.record_failure(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_credentials", "message": "Invalid email or password."},
        )

    if not verify_password(req.password, user.password_hash) or user.status != "active":
        login_rate_limiter.record_failure(email_clean)
        login_rate_limiter.record_failure(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_credentials", "message": "Invalid email or password."},
        )

    # Success: reset rate limiter
    login_rate_limiter.reset(email_clean)
    login_rate_limiter.reset(client_ip)

    # Issue session & CSRF tokens
    raw_session_token = generate_secure_token(32)
    raw_csrf_token = generate_secure_token(32)

    new_session = Session(
        user_id=user.id,
        token_hash=hash_token(raw_session_token),
        csrf_token_hash=hash_token(raw_csrf_token),
        expires_at=utc_now() + timedelta(seconds=settings.SESSION_MAX_AGE_SECONDS),
    )
    db.add(new_session)
    await db.commit()

    # Set HttpOnly, SameSite=Lax cookie (Secure over TLS)
    is_tls = request_is_tls(request) or settings.ENVIRONMENT == "production"
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=raw_session_token,
        max_age=settings.SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=is_tls,
        path="/",
    )
    response.headers["X-CSRF-Token"] = raw_csrf_token

    return LoginResponse(
        user=_user_response(user),
        csrf_token=raw_csrf_token,
    )


@router.post("/auth/logout")
async def logout(
    response: Response,
    session_data: tuple[Session, User] | None = Depends(get_current_session_and_user),
    _csrf: None = Depends(verify_csrf),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """AC-05: Invalidate active session and clear cookie."""
    if session_data:
        session, _ = session_data
        session.revoked_at = utc_now()
        await db.commit()

    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return {"message": "Logged out successfully."}


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(require_authenticated_user)) -> UserResponse:
    """Return authenticated caller's profile."""
    return _user_response(user)


@router.patch("/me", response_model=UserResponse, dependencies=[Depends(verify_csrf)])
async def update_me(
    req: UpdateMeRequest,
    user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Spec 9 / AC-72: update display name and the match-email preference."""
    if req.display_name is not None:
        user.display_name = req.display_name.strip() or None
    if req.notify_match_email is not None:
        user.notify_match_email = req.notify_match_email
    await db.commit()
    return _user_response(user)


@router.get("/auth/csrf", response_model=CsrfResponse)
async def refresh_csrf_token(
    session_data: tuple[Session, User] | None = Depends(get_current_session_and_user),
    db: AsyncSession = Depends(get_db),
) -> CsrfResponse:
    """Issue a fresh CSRF token for the current session (e.g. after a page reload).

    Only the hash is stored. The response is readable only by same-origin scripts (CORS is
    limited to the configured origin), so a cross-site page cannot obtain the token.
    """
    if session_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Authentication required."},
        )
    session, _ = session_data
    raw_csrf_token = generate_secure_token(32)
    session.csrf_token_hash = hash_token(raw_csrf_token)
    await db.commit()
    return CsrfResponse(csrf_token=raw_csrf_token)


@router.get("/me/export")
async def export_my_data(
    user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """AC-104: Export user's personal data as JSON."""
    from app.services.user_account import export_user_data

    return await export_user_data(db, user)


@router.delete("/me", dependencies=[Depends(verify_csrf)])
async def delete_me(
    response: Response,
    user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """AC-103: Delete user account, scrub personal data, anonymise reports, and clear cookie."""
    from app.services.user_account import delete_user_account

    await delete_user_account(db, user)
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return {"status": "deleted", "message": "Account deleted and data anonymized."}
