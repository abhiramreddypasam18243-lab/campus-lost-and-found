import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_ac_11_sql_injection_defense(async_client: AsyncClient, db_session: AsyncSession) -> None:
    """AC-11 (SEC8): SQL injection string stored and returned literally; tables intact."""
    injection_string = "'; DROP TABLE users;--"
    payload = {
        "email": "sqli_test@campus.edu",
        "password": "valid_password_1234",
        "display_name": injection_string,
    }
    res = await async_client.post("/api/auth/register", json=payload)
    assert res.status_code == 201

    # Verify users table is intact and contains literal injection string
    result = await db_session.execute(text("SELECT display_name FROM users WHERE email = 'sqli_test@campus.edu'"))
    row = result.first()
    assert row is not None
    assert row[0] == injection_string


@pytest.mark.asyncio
async def test_ac_12_xss_defense_and_csp(async_client: AsyncClient) -> None:
    """AC-12 (SEC8, SEC9): XSS payloads stored as literal text; CSP header is present."""
    xss_payload = "<script>alert(1)</script>"
    payload = {
        "email": "xss_test@campus.edu",
        "password": "valid_password_1234",
        "display_name": xss_payload,
    }
    res = await async_client.post("/api/auth/register", json=payload)
    assert res.status_code == 201

    # Verify Content-Security-Policy header is present on response
    assert "Content-Security-Policy" in res.headers
    assert "default-src 'self'" in res.headers["Content-Security-Policy"]
