import time
import uuid
from datetime import UTC, date, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.jobs import BackgroundJob
from app.models.location import CampusLocation
from app.models.user import User


@pytest.fixture
async def report_creator_auth(
    db_session: AsyncSession, async_client: AsyncClient
) -> dict[str, any]:
    user = User(
        email="reporter_jobs@campus.edu",
        password_hash=hash_password("Pass1234!"),
        role="user",
        email_verified_at=datetime.now(UTC),
    )
    loc = CampusLocation(name="Student Center", kind="building")
    db_session.add_all([user, loc])
    await db_session.commit()

    login_res = await async_client.post(
        "/api/auth/login",
        json={"email": "reporter_jobs@campus.edu", "password": "Pass1234!"},
    )
    return {
        "user": user,
        "location": loc,
        "cookies": {"session_id": login_res.cookies.get("session_id", "")},
        "csrf_token": login_res.headers.get("X-CSRF-Token") or login_res.json()["csrf_token"],
    }


@pytest.mark.asyncio
async def test_ac_45_saving_report_enqueues_embedding_job(
    async_client: AsyncClient, db_session: AsyncSession, report_creator_auth: dict[str, any]
) -> None:
    """AC-45: Saving a report enqueues its embedding jobs and returns under 300ms."""
    cookies = report_creator_auth["cookies"]
    headers = {"X-CSRF-Token": report_creator_auth["csrf_token"]}
    loc_id = report_creator_auth["location"].id

    payload = {
        "title": "Blue Dell Laptop",
        "description": "Inspiron 15-inch blue laptop in black sleeve.",
        "category": "laptop_tablet",
        "location_id": str(loc_id),
        "date": str(date.today()),
        "time_precision": "afternoon",
    }

    start = time.perf_counter()
    res = await async_client.post(
        "/api/reports/lost", json=payload, cookies=cookies, headers=headers
    )
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert res.status_code == 201, res.text
    report_id = uuid.UUID(res.json()["id"])

    # Check latency target (< 300 ms with models off)
    assert elapsed_ms < 300, f"Endpoint took {elapsed_ms:.1f}ms, target < 300ms"

    # Verify background job was enqueued in the database in the same transaction
    stmt = select(BackgroundJob).where(
        BackgroundJob.entity_id == report_id,
        BackgroundJob.kind == "embed_report_text",
    )
    job = (await db_session.execute(stmt)).scalar_one_or_none()
    assert job is not None
    assert job.status == "pending"
    assert job.attempts == 0
