import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ac_03_password_length_validation(async_client: AsyncClient) -> None:
    """AC-03 (SEC1): Passwords of 11 chars rejected (422), 12 and 128 accepted, 129 rejected (422)."""
    # 1. 11 characters -> rejected with 422
    res_11 = await async_client.post(
        "/api/auth/register",
        json={"email": "pwd11@campus.edu", "password": "a" * 11},
    )
    assert res_11.status_code == 422

    # 2. 12 characters -> accepted (201)
    res_12 = await async_client.post(
        "/api/auth/register",
        json={"email": "pwd12@campus.edu", "password": "a" * 12},
    )
    assert res_12.status_code == 201

    # 3. 128 characters -> accepted (201)
    res_128 = await async_client.post(
        "/api/auth/register",
        json={"email": "pwd128@campus.edu", "password": "b" * 128},
    )
    assert res_128.status_code == 201

    # 4. 129 characters -> rejected with 422
    res_129 = await async_client.post(
        "/api/auth/register",
        json={"email": "pwd129@campus.edu", "password": "c" * 129},
    )
    assert res_129.status_code == 422
