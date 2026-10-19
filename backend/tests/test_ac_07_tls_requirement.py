from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import hash_password
from app.main import app
from app.models.user import User


@pytest.mark.asyncio
async def test_ac_07_tls_required_for_remote_client(db_session: AsyncSession) -> None:
    """AC-07 (SEC7): Plain HTTP login from non-localhost client returns 403 tls_required."""
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    user = User(
        email="tls_user@campus.edu",
        password_hash=hash_password("valid_password_1234"),
        role="user",
    )
    db_session.add(user)
    await db_session.commit()

    # Remote non-localhost client over HTTP
    transport_remote_http = ASGITransport(
        app=app,
        client=("192.168.1.100", 50000),
    )
    async with AsyncClient(transport=transport_remote_http, base_url="http://campus.edu") as client:
        res = await client.post(
            "/api/auth/login",
            json={"email": "tls_user@campus.edu", "password": "valid_password_1234"},
        )
        assert res.status_code == 403
        assert "tls_required" in str(res.json())

    # Remote client attempting forged X-Forwarded-Proto
    async with AsyncClient(transport=transport_remote_http, base_url="http://campus.edu") as client:
        res = await client.post(
            "/api/auth/login",
            json={"email": "tls_user@campus.edu", "password": "valid_password_1234"},
            headers={"X-Forwarded-Proto": "https"},
        )
        assert res.status_code == 403

    # Remote client over HTTPS succeeds
    transport_remote_https = ASGITransport(
        app=app,
        client=("192.168.1.100", 50000),
    )
    async with AsyncClient(transport=transport_remote_https, base_url="https://campus.edu") as client:
        res = await client.post(
            "/api/auth/login",
            json={"email": "tls_user@campus.edu", "password": "valid_password_1234"},
        )
        assert res.status_code == 200

    app.dependency_overrides.clear()
