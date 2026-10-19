import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.jobs import BackgroundJob
from app.models.user import User
from app.services.job_queue import handle_job_failure


@pytest.fixture
async def admin_auth(db_session: AsyncSession, async_client: AsyncClient) -> dict[str, any]:
    admin = User(
        email="admin_jobs@campus.edu",
        password_hash=hash_password("AdminPass123!"),
        role="admin",
        email_verified_at=datetime.now(UTC),
    )
    student = User(
        email="student_jobs@campus.edu",
        password_hash=hash_password("StudentPass123!"),
        role="user",
        email_verified_at=datetime.now(UTC),
    )
    db_session.add_all([admin, student])
    await db_session.commit()

    res_admin = await async_client.post(
        "/api/auth/login",
        json={"email": "admin_jobs@campus.edu", "password": "AdminPass123!"},
    )
    admin_csrf = res_admin.headers.get("X-CSRF-Token") or res_admin.json()["csrf_token"]
    admin_cookies = {"session_id": res_admin.cookies.get("session_id", "")}

    res_stud = await async_client.post(
        "/api/auth/login",
        json={"email": "student_jobs@campus.edu", "password": "StudentPass123!"},
    )
    stud_cookies = {"session_id": res_stud.cookies.get("session_id", "")}

    return {
        "admin": admin,
        "admin_cookies": admin_cookies,
        "admin_csrf": admin_csrf,
        "stud_cookies": stud_cookies,
    }


@pytest.mark.asyncio
async def test_ac_47_retry_backoff_and_admin_manual_retry(
    async_client: AsyncClient, db_session: AsyncSession, admin_auth: dict[str, any]
) -> None:
    """AC-47: Failing job retries after 1, 2, 4, 8 min, fails after 5 attempts, appears on admin page, manual retry works."""
    admin_cookies = admin_auth["admin_cookies"]
    admin_csrf = admin_auth["admin_csrf"]
    stud_cookies = admin_auth["stud_cookies"]

    base_time = datetime(2026, 10, 19, 12, 0, 0, tzinfo=UTC)
    job = BackgroundJob(
        kind="flaky_task",
        entity_id=uuid.uuid4(),
        status="running",
        attempts=0,
        run_after=base_time,
    )
    db_session.add(job)
    await db_session.commit()

    # Backoff sequence: 1, 2, 4, 8 minutes
    expected_backoffs = [1, 2, 4, 8]
    curr_time = base_time

    for expected_minutes in expected_backoffs:
        handle_job_failure(job, error_msg="Transient failure", current_time=curr_time)
        await db_session.commit()
        await db_session.refresh(job)

        assert job.status == "pending"
        expected_run_after = curr_time + timedelta(minutes=expected_minutes)
        assert job.run_after == expected_run_after
        curr_time = expected_run_after

    # 5th failure -> status becomes "failed"
    handle_job_failure(job, error_msg="Permanent failure", current_time=curr_time)
    await db_session.commit()
    await db_session.refresh(job)

    assert job.attempts == 5
    assert job.status == "failed"
    assert job.last_error == "Permanent failure"

    # 6. Non-admin accessing admin jobs endpoint returns 404
    res_forbidden = await async_client.get("/api/admin/jobs?status=failed", cookies=stud_cookies)
    assert res_forbidden.status_code == 404

    # 7. Admin sees failed job in list
    res_admin = await async_client.get("/api/admin/jobs?status=failed", cookies=admin_cookies)
    assert res_admin.status_code == 200
    failed_jobs = res_admin.json()["jobs"]
    assert any(j["id"] == str(job.id) for j in failed_jobs)

    # 8. Admin triggers manual retry
    res_retry = await async_client.post(
        f"/api/admin/jobs/{job.id}/retry",
        cookies=admin_cookies,
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert res_retry.status_code == 200
    await db_session.refresh(job)

    assert job.status == "pending"
    assert job.attempts == 0
    assert job.last_error is None
    assert job.run_after <= datetime.now(UTC)
