"""Tests for AC-97 to AC-104: Retention, deletion, export, and audit log immutability."""

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_token
from app.models.audit import AuditLog
from app.models.embeddings import ImageEmbedding
from app.models.location import CampusLocation
from app.models.notifications import Notification
from app.models.report import ItemImage, ItemReport
from app.models.user import Session, User
from app.services.retention import (
    expire_unclaimed_reports,
    purge_closed_images,
    purge_old_audit_logs,
)


async def create_user_and_cookie(
    async_client: AsyncClient,
    db_session: AsyncSession,
    email: str,
    role: str = "user",
) -> tuple[User, dict[str, str], str]:
    now = datetime.now(UTC)
    user = User(
        email=email,
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$fakehash",
        role=role,
        status="active",
        email_verified_at=now,
    )
    db_session.add(user)
    await db_session.flush()

    raw_sid = f"sess_{uuid.uuid4()}"
    raw_csrf = f"csrf_{uuid.uuid4()}"
    sess = Session(
        user_id=user.id,
        token_hash=hash_token(raw_sid),
        csrf_token_hash=hash_token(raw_csrf),
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
    )
    db_session.add(sess)
    await db_session.commit()

    return user, {"session_id": raw_sid}, raw_csrf


@pytest.mark.asyncio
async def test_ac_97_audit_log_immutable(db_session: AsyncSession) -> None:
    """AC-97: Raw SQL UPDATE or DELETE on the audit table fails because of the database trigger."""
    entry_id = uuid.uuid4()
    entry = AuditLog(
        id=entry_id,
        actor_id=uuid.uuid4(),
        role="admin",
        action="test.action",
        entity_type="test",
        entity_id=uuid.uuid4(),
        summary={"foo": "bar"},
    )
    db_session.add(entry)
    await db_session.commit()

    # 1. Raw UPDATE must fail
    with pytest.raises(DBAPIError) as exc_update:
        await db_session.execute(
            text("UPDATE audit_log SET action = 'tampered' WHERE id = :id;"),
            {"id": entry_id},
        )
    assert "audit_log is append-only: updates are prohibited" in str(exc_update.value)
    await db_session.rollback()

    # 2. Raw DELETE without privileged role must fail
    with pytest.raises(DBAPIError) as exc_delete:
        await db_session.execute(
            text("DELETE FROM audit_log WHERE id = :id;"),
            {"id": entry_id},
        )
    assert "audit_log is append-only: deletes are prohibited" in str(exc_delete.value)
    await db_session.rollback()


@pytest.mark.asyncio
async def test_ac_98_and_99_role_change_and_last_admin_guard(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC-98 & AC-99: Role changes are admin-only, audited, and the last admin cannot be demoted or deleted."""
    admin1, a1_cookies, a1_csrf = await create_user_and_cookie(
        async_client, db_session, "admin1@campus.edu", role="admin"
    )
    mod1, _, _ = await create_user_and_cookie(
        async_client, db_session, "mod1@campus.edu", role="moderator"
    )
    user1, u1_cookies, u1_csrf = await create_user_and_cookie(
        async_client, db_session, "user1@campus.edu", role="user"
    )

    headers_admin = {"X-CSRF-Token": a1_csrf}
    headers_user = {"X-CSRF-Token": u1_csrf}

    # 1. Non-admin attempting to change role gets 404 anti-enumeration
    non_admin_res = await async_client.patch(
        f"/api/admin/users/{mod1.id}/role",
        cookies=u1_cookies,
        headers=headers_user,
        json={"role": "admin"},
    )
    assert non_admin_res.status_code == 404

    # 2. Demoting the only admin returns 409 last_admin_cannot_be_demoted
    demote_sole_res = await async_client.patch(
        f"/api/admin/users/{admin1.id}/role",
        cookies=a1_cookies,
        headers=headers_admin,
        json={"role": "user"},
    )
    assert demote_sole_res.status_code == 409
    assert demote_sole_res.json()["detail"] == "last_admin_cannot_be_demoted"

    # 3. Promote user1 to admin -> now 2 admins exist
    promote_res = await async_client.patch(
        f"/api/admin/users/{user1.id}/role",
        cookies=a1_cookies,
        headers=headers_admin,
        json={"role": "admin"},
    )
    assert promote_res.status_code == 200
    assert promote_res.json()["role"] == "admin"

    # Verify audit log was written for role change (AC-98)
    audit_stmt = select(AuditLog).where(
        AuditLog.action == "role.changed", AuditLog.entity_id == user1.id
    )
    audit_row = (await db_session.execute(audit_stmt)).scalar_one_or_none()
    assert audit_row is not None
    assert audit_row.summary["old_role"] == "user"
    assert audit_row.summary["new_role"] == "admin"

    # 4. Now admin1 can be demoted because user1 is an admin
    demote_res = await async_client.patch(
        f"/api/admin/users/{admin1.id}/role",
        cookies=a1_cookies,
        headers=headers_admin,
        json={"role": "moderator"},
    )
    assert demote_res.status_code == 200
    assert demote_res.json()["role"] == "moderator"


@pytest.mark.asyncio
async def test_ac_100_unclaimed_reports_retention_and_disposition(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC-100: Found report still 'open' after 90 days becomes 'unclaimed_expired' and disposition recorded."""
    finder, _, _ = await create_user_and_cookie(async_client, db_session, "finder100@campus.edu")
    mod, mod_cookies, mod_csrf = await create_user_and_cookie(
        async_client, db_session, "mod100@campus.edu", role="moderator"
    )

    loc = CampusLocation(name=f"Hall {uuid.uuid4().hex[:6]}", kind="building")
    db_session.add(loc)
    await db_session.flush()

    # Found report created 95 days ago
    t_past = datetime.now(UTC) - timedelta(days=95)
    report = ItemReport(
        type="found",
        status="open",
        title="Forgotten Coat",
        description="Winter coat left in locker room",
        category="clothing",
        verification_prompts=[],
        window_start=t_past,
        window_end=t_past,
        time_precision="exact",
        location_id=loc.id,
        reporter_id=finder.id,
        created_at=t_past,
        updated_at=t_past,
    )
    db_session.add(report)
    await db_session.commit()

    report_id = report.id

    # Run retention sweep
    expired_count = await expire_unclaimed_reports(db_session, retention_days=90)
    assert expired_count >= 1

    await db_session.rollback()
    res = await db_session.execute(select(ItemReport.status).where(ItemReport.id == report_id))
    assert res.scalar_one() == "unclaimed_expired"

    # Moderator records disposition
    disp_res = await async_client.post(
        f"/api/mod/reports/{report_id}/disposition",
        cookies=mod_cookies,
        headers={"X-CSRF-Token": mod_csrf},
        json={"disposition": "donated"},
    )
    assert disp_res.status_code == 200
    assert disp_res.json()["disposition"] == "donated"

    await db_session.rollback()
    res2 = await db_session.execute(
        select(ItemReport.disposition).where(ItemReport.id == report_id)
    )
    assert res2.scalar_one() == "donated"


@pytest.mark.asyncio
async def test_ac_101_purge_closed_images(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-101: Images are deleted 30 days after their report closes and claim evidence 30 days after claim closes."""
    settings = get_settings()
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

    finder, _, _ = await create_user_and_cookie(None, db_session, "finder101@campus.edu")  # type: ignore[arg-type]
    loc = CampusLocation(name=f"Hall {uuid.uuid4().hex[:6]}", kind="building")
    db_session.add(loc)
    await db_session.flush()

    t_closed = datetime.now(UTC) - timedelta(days=35)
    report = ItemReport(
        type="found",
        status="closed",
        title="Old Closed Item",
        description="Description of old closed item",
        category="accessory",
        verification_prompts=[],
        window_start=t_closed,
        window_end=t_closed,
        time_precision="exact",
        location_id=loc.id,
        reporter_id=finder.id,
        closed_at=t_closed,
        created_at=t_closed,
        updated_at=t_closed,
    )
    db_session.add(report)
    await db_session.flush()

    # Create dummy image files in tmp_path
    storage_key = f"img_{uuid.uuid4().hex}.jpg"
    thumb_key = f"thumb_{storage_key}"
    (tmp_path / storage_key).write_bytes(b"mock_image_bytes")
    (tmp_path / thumb_key).write_bytes(b"mock_thumb_bytes")

    img = ItemImage(
        report_id=report.id,
        storage_key=storage_key,
        original_mime="image/jpeg",
        sha256="fake_sha",
        dhash="0000000000000000",
        width=100,
        height=100,
        is_public=True,
        moderation_status="approved",
    )
    db_session.add(img)
    await db_session.flush()

    # Add mock image embedding
    emb = ImageEmbedding(
        entity_id=img.id,
        model_name="clip-test",
        model_version="v1",
        dimension=512,
        vector=[0.0] * 512,
    )
    db_session.add(emb)
    await db_session.commit()

    # Run purge
    purged_count = await purge_closed_images(db_session, purge_days=30)
    assert purged_count >= 1

    # Verify physical files removed
    assert not (tmp_path / storage_key).exists()
    assert not (tmp_path / thumb_key).exists()

    # Verify DB record marked deleted
    await db_session.rollback()
    refreshed_img = await db_session.get(ItemImage, img.id)
    assert refreshed_img.deleted_at is not None

    # Verify embedding deleted
    emb_stmt = select(ImageEmbedding).where(ImageEmbedding.entity_id == img.id)
    assert (await db_session.execute(emb_stmt)).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_ac_102_privileged_audit_log_purge(db_session: AsyncSession) -> None:
    """AC-102: Audit rows older than 365 days can be removed only by the retention job's privileged role."""
    t_old = datetime.now(UTC) - timedelta(days=400)
    t_recent = datetime.now(UTC) - timedelta(days=30)

    old_log = AuditLog(
        actor_id=uuid.uuid4(),
        role="admin",
        action="old.action",
        entity_type="test",
        entity_id=uuid.uuid4(),
        created_at=t_old,
    )
    recent_log = AuditLog(
        actor_id=uuid.uuid4(),
        role="admin",
        action="recent.action",
        entity_type="test",
        entity_id=uuid.uuid4(),
        created_at=t_recent,
    )
    db_session.add_all([old_log, recent_log])
    await db_session.commit()

    # Purge logs older than 365 days
    deleted_count = await purge_old_audit_logs(db_session, retention_days=365)
    assert deleted_count >= 1

    await db_session.rollback()
    assert await db_session.get(AuditLog, old_log.id) is None
    assert await db_session.get(AuditLog, recent_log.id) is not None


@pytest.mark.asyncio
async def test_ac_103_account_deletion_scrubbing_and_anonymization(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC-103: Deleting an account removes personal data, anonymises reports,

    closes open reports, revokes sessions, and leaves 0 occurrences of email.
    """
    secret_email = "sensitive_student_103@campus.edu"
    user, user_cookies, user_csrf = await create_user_and_cookie(
        async_client, db_session, secret_email, role="user"
    )

    loc = CampusLocation(name=f"Hall {uuid.uuid4().hex[:6]}", kind="building")
    db_session.add(loc)
    await db_session.flush()

    # User's open report with private details
    report = ItemReport(
        type="found",
        status="open",
        title="Student Wallet",
        description="Leather wallet",
        category="wallet",
        private_details="Contains driver license for John Doe",
        verification_prompts=[],
        window_start=datetime.now(UTC),
        window_end=datetime.now(UTC),
        time_precision="exact",
        location_id=loc.id,
        reporter_id=user.id,
    )
    db_session.add(report)

    # User's notification
    notif = Notification(
        user_id=user.id,
        event_type="claim_update",
        event_key=f"k_{uuid.uuid4()}",
        payload={"msg": "hello"},
    )
    db_session.add(notif)
    await db_session.commit()

    user_id = user.id
    report_id = report.id

    # User requests account deletion
    del_res = await async_client.delete(
        "/api/me",
        cookies=user_cookies,
        headers={"X-CSRF-Token": user_csrf},
    )
    assert del_res.status_code == 200

    # 1. Old session is revoked -> immediate 401 on next request (AC-05)
    subsequent_res = await async_client.get("/api/me", cookies=user_cookies)
    assert subsequent_res.status_code == 401

    # 2. Check DB: reports closed, private details scrubbed
    await db_session.rollback()
    r_stmt = select(ItemReport.status, ItemReport.private_details).where(ItemReport.id == report_id)
    r_status, r_priv = (await db_session.execute(r_stmt)).one()
    assert r_status == "closed"
    assert r_priv is None

    # 3. Notifications deleted
    notif_check = select(func.count(Notification.id)).where(Notification.user_id == user_id)
    assert (await db_session.execute(notif_check)).scalar() == 0

    # 4. Email completely wiped from users table
    u_stmt = select(User.email, User.display_name).where(User.id == user_id)
    u_email, u_name = (await db_session.execute(u_stmt)).one()
    assert secret_email not in u_email
    assert u_email.endswith("@anonymized.local")
    assert u_name == "Deleted User"

    # 5. Raw text check: secret_email appears 0 times across all users
    scan_stmt = select(func.count(User.id)).where(User.email == secret_email)
    assert (await db_session.execute(scan_stmt)).scalar() == 0


@pytest.mark.asyncio
async def test_ac_104_data_export_isolation(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC-104: Data export contains the user's own data and no one else's data."""
    u1, u1_cookies, _ = await create_user_and_cookie(
        async_client, db_session, "export_u1@campus.edu"
    )
    u2, _, _ = await create_user_and_cookie(async_client, db_session, "export_u2@campus.edu")

    loc = CampusLocation(name=f"Hall {uuid.uuid4().hex[:6]}", kind="building")
    db_session.add(loc)
    await db_session.flush()

    now = datetime.now(UTC)
    r1 = ItemReport(
        type="lost",
        status="open",
        title="U1 Lost Bag",
        description="Blue bag",
        category="bag",
        verification_prompts=[],
        window_start=now,
        window_end=now,
        time_precision="exact",
        location_id=loc.id,
        reporter_id=u1.id,
    )
    r2 = ItemReport(
        type="lost",
        status="open",
        title="U2 Lost Keys",
        description="Key bundle",
        category="keys",
        verification_prompts=[],
        window_start=now,
        window_end=now,
        time_precision="exact",
        location_id=loc.id,
        reporter_id=u2.id,
    )
    db_session.add_all([r1, r2])
    await db_session.commit()

    # U1 exports data
    export_res = await async_client.get("/api/me/export", cookies=u1_cookies)
    assert export_res.status_code == 200
    export_data = export_res.json()

    assert export_data["user"]["email"] == "export_u1@campus.edu"
    report_titles = [r["title"] for r in export_data["reports"]]
    assert "U1 Lost Bag" in report_titles
    assert "U2 Lost Keys" not in report_titles
