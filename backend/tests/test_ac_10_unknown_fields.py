import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ac_10_unknown_fields_forbidden(async_client: AsyncClient) -> None:
    """AC-10 (SEC8): Request body with unknown field (e.g. reporter_id) rejected with 422."""
    payload_register = {
        "email": "test_extra@campus.edu",
        "password": "valid_password_1234",
        "reporter_id": "00000000-0000-0000-0000-000000000000",
    }
    res_reg = await async_client.post("/api/auth/register", json=payload_register)
    assert res_reg.status_code == 422
    assert "extra_forbidden" in str(res_reg.json()) or "extra fields not permitted" in str(res_reg.json())

    payload_login = {
        "email": "test_extra@campus.edu",
        "password": "valid_password_1234",
        "claimant_id": "00000000-0000-0000-0000-000000000000",
    }
    res_login = await async_client.post("/api/auth/login", json=payload_login)
    assert res_login.status_code == 422
