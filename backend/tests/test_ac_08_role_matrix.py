import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_secure_token, hash_password, hash_token, utc_now
from app.models.user import Session, User


async def create_user_with_session(
    db: AsyncSession,
    email: str,
    role: str,
) -> tuple[User, str]:
    """Helper to create a user with an active session."""
    user = User(
        email=email,
        password_hash=hash_password("valid_password_1234"),
        role=role,
        email_verified_at=utc_now(),
    )
    db.add(user)
    await db.flush()

    raw_token = generate_secure_token()
    session = Session(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        csrf_token_hash=hash_token("csrf_token"),
        expires_at=utc_now() + pytest.importorskip("datetime").timedelta(days=1),
    )
    db.add(session)
    await db.commit()
    return user, raw_token


@pytest.mark.asyncio
async def test_ac_08_role_matrix(async_client: AsyncClient, db_session: AsyncSession) -> None:
    """AC-08 (SEC4): Check route access against section 3 role matrix."""
    # Create accounts for each role
    _, user_token = await create_user_with_session(db_session, "user1@campus.edu", "user")
    _, mod_token = await create_user_with_session(db_session, "mod1@campus.edu", "moderator")
    _, admin_token = await create_user_with_session(db_session, "admin1@campus.edu", "admin")

    tokens = {
        "anonymous": None,
        "user": user_token,
        "moderator": mod_token,
        "admin": admin_token,
    }

    # Matrix check on /api/me:
    # Anonymous: 401
    # User: 200
    # Moderator: 200
    # Admin: 200
    for role, tok in tokens.items():
        cookies = {"session_id": tok} if tok else {}
        res = await async_client.get("/api/me", cookies=cookies)
        if role == "anonymous":
            assert res.status_code == 401, f"Expected 401 for anonymous on /api/me, got {res.status_code}"
        else:
            assert res.status_code == 200, f"Expected 200 for {role} on /api/me, got {res.status_code}"
            data = res.json()
            assert data["role"] == role
