from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
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
    async with AsyncClient(
        transport=transport_remote_https, base_url="https://campus.edu"
    ) as client:
        res = await client.post(
            "/api/auth/login",
            json={"email": "tls_user@campus.edu", "password": "valid_password_1234"},
        )
        assert res.status_code == 200

    app.dependency_overrides.clear()


async def _login(
    client_ip: str, headers: dict[str, str] | None = None, scheme: str = "http"
) -> tuple[int, str]:
    transport = ASGITransport(app=app, client=(client_ip, 50000))
    async with AsyncClient(transport=transport, base_url=f"{scheme}://campus.edu") as client:
        res = await client.post(
            "/api/auth/login",
            json={"email": "proxy_user@campus.edu", "password": "valid_password_1234"},
            headers=headers or {},
        )
        return res.status_code, res.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_ac_07_forwarded_headers_trusted_only_from_configured_proxy(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SEC7: only the configured proxy may vouch for HTTPS or for a loopback client.

    Regression: any 172.* address used to be treated as a proxy, and development mode accepted
    every proxied login, so LAN clients reaching Docker-published ports could log in over HTTP.
    """

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(settings, "TRUSTED_PROXIES_RAW", "10.9.8.7")
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    db_session.add(
        User(
            email="proxy_user@campus.edu",
            password_hash=hash_password("valid_password_1234"),
            role="user",
        )
    )
    await db_session.commit()
    try:
        # A Docker-network peer that is not the configured proxy cannot forge either header.
        assert (await _login("172.18.0.5", {"X-Forwarded-Proto": "https"}))[0] == 403
        assert (await _login("172.18.0.5", {"X-Client-Network": "loopback"}))[0] == 403
        assert (await _login("172.18.0.5"))[0] == 403

        # The configured proxy: HTTPS is trusted and the session cookie is Secure.
        status, cookie = await _login("10.9.8.7", {"X-Forwarded-Proto": "https"})
        assert status == 200
        assert "secure" in cookie.lower()

        # The proxy's loopback-only plain-HTTP listener (this machine) works, without Secure.
        status, cookie = await _login(
            "10.9.8.7", {"X-Forwarded-Proto": "http", "X-Client-Network": "loopback"}
        )
        assert status == 200
        assert "secure" not in cookie.lower()

        # Plain HTTP through the proxy from the network is refused.
        lan = {"X-Forwarded-Proto": "http", "X-Client-Network": "lan"}
        assert (await _login("10.9.8.7", lan))[0] == 403
    finally:
        app.dependency_overrides.clear()
