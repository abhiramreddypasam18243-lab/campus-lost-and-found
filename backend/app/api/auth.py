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
    verify_dummy_password,
    verify_password,
)
from app.models.user import EmailToken, Session, User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    UserResponse,
    VerifyEmailRequest,
)
from app.services.audit import write_audit_log

router = APIRouter(prefix="/api", tags=["auth"])
settings = get_settings()


def is_valid_college_domain(domain: str) -> bool:
    """Validate that the domain belongs to a university, college, or institutional campus."""
    d = domain.lower().strip()
    allowed_list = [item.lower().strip() for item in settings.ALLOWED_EMAIL_DOMAINS]

    if "*" in allowed_list or d in allowed_list:
        return True

    # Block common free personal email providers
    blocked_providers = {
        "gmail.com",
        "yahoo.com",
        "yahoo.co.in",
        "hotmail.com",
        "outlook.com",
        "live.com",
        "icloud.com",
        "aol.com",
        "proton.me",
        "protonmail.com",
        "zoho.com",
        "mail.com",
        "yandex.com",
        "gmx.com",
    }
    if d in blocked_providers:
        return False

    # Institutional & Academic suffixes globally (.ac.in, .edu.in, .edu, .ac.uk, etc.)
    academic_suffixes = (
        ".edu",
        ".ac.in",
        ".edu.in",
        ".res.in",
        ".ac.uk",
        ".edu.au",
        ".ac.nz",
        ".edu.sg",
        ".edu.cn",
        ".ac.za",
        ".ac.jp",
        ".edu.my",
        ".edu.hk",
        ".ac.kr",
        ".edu.pk",
        ".edu.ph",
        ".ac.th",
        ".edu.bd",
        ".edu.eg",
        ".edu.ng",
        ".ac.be",
        ".ac.at",
        ".ac.il",
        ".ac.rs",
        ".ac.rw",
        ".edu.co",
        ".edu.mx",
        ".edu.br",
        ".edu.ar",
        ".edu.tr",
        ".edu.sa",
        ".edu.qa",
    )
    if any(d.endswith(suffix) for suffix in academic_suffixes):
        return True

    # Common college naming keywords (e.g. xyzcollege.org, abcuniv.org)
    institutional_keywords = ("campus", "univ", "college", "institute", "academy", "school")
    if any(kw in d for kw in institutional_keywords):
        return True

    return False


@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register(
    req: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """AC-01: Register user with allowed campus or college email domain."""
    email_clean = req.email.strip().lower()
    domain = email_clean.split("@")[-1]

    # Validate institutional/college email domain
    if not is_valid_college_domain(domain):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "email_domain_not_allowed",
                "message": f"Domain '@{domain}' is not recognized as an institutional or college email. Please use your official university email (e.g. .edu, .ac.in, .edu.in).",
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

    # Create verification token (expires in 24 hours per AC-02)
    raw_token = generate_secure_token()
    token_entry = EmailToken(
        user_id=new_user.id,
        token_hash=hash_token(raw_token),
        purpose="verify_email",
        expires_at=utc_now() + timedelta(hours=24),
    )
    db.add(token_entry)

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

    return {"message": "Account created. Verification link sent to email.", "email": email_clean}


@router.post("/auth/verify-email")
async def verify_email(
    req: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """AC-02: Verify email using single-use token."""
    token_hash = hash_token(req.token)
    now = utc_now()

    stmt = select(EmailToken).where(
        EmailToken.token_hash == token_hash,
        EmailToken.purpose == "verify_email",
    )
    token_entry = (await db.execute(stmt)).scalar_one_or_none()

    # Reused or expired link returns 410 per AC-02
    if not token_entry or token_entry.used_at is not None or token_entry.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={
                "code": "token_expired_or_invalid",
                "message": "Verification link has expired or been used.",
            },
        )

    # Mark token used and user verified
    token_entry.used_at = now
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
    is_tls = request.url.scheme == "https" or settings.ENVIRONMENT == "production"
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
        user=UserResponse(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            email_verified=user.email_verified_at is not None,
            created_at=user.created_at,
        ),
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
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        email_verified=user.email_verified_at is not None,
        created_at=user.created_at,
    )


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
