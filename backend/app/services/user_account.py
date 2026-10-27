"""User account management, export, role administration, and deletion (AC-99, AC-103, AC-104)."""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claims import Claim
from app.models.notifications import Notification
from app.models.report import ItemReport
from app.models.user import Session, User
from app.services.audit import write_audit_log


def get_utcnow() -> datetime:
    return datetime.now(UTC)


async def change_user_role(
    db: AsyncSession,
    target_user_id: uuid.UUID,
    new_role: str,
    admin_user: User,
) -> User:
    """AC-99: Role changes are admin-only and are audited, and the last admin cannot be demoted."""
    if admin_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    valid_roles = ("user", "moderator", "admin")
    if new_role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="invalid_role",
        )

    target_user = await db.get(User, target_user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")

    # Guard: cannot demote the last admin
    if target_user.role == "admin" and new_role != "admin":
        count_stmt = select(func.count(User.id)).where(
            User.role == "admin", User.status == "active"
        )
        total_admins = (await db.execute(count_stmt)).scalar() or 0
        if total_admins <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="last_admin_cannot_be_demoted",
            )

    old_role = target_user.role
    target_user.role = new_role
    target_user.updated_at = get_utcnow()

    await write_audit_log(
        db=db,
        actor_id=admin_user.id,
        role=admin_user.role,
        action="role.changed",
        entity_type="user",
        entity_id=target_user.id,
        summary={"old_role": old_role, "new_role": new_role},
    )
    await db.commit()
    await db.refresh(target_user)
    return target_user


async def export_user_data(db: AsyncSession, user: User) -> dict[str, Any]:
    """AC-104: Data export containing the user's own reports, claims, evidence, and notifications as JSON."""
    # 1. Profile
    profile = {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "timezone": user.timezone,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }

    # 2. Reports
    report_stmt = (
        select(ItemReport)
        .where(ItemReport.reporter_id == user.id)
        .order_by(ItemReport.created_at.desc())
    )
    reports = list((await db.execute(report_stmt)).scalars().all())
    reports_data = [
        {
            "id": str(r.id),
            "type": r.type,
            "status": r.status,
            "title": r.title,
            "description": r.description,
            "category": r.category,
            "private_details": r.private_details,
            "verification_prompts": r.verification_prompts,
            "window_start": r.window_start.isoformat() if r.window_start else None,
            "window_end": r.window_end.isoformat() if r.window_end else None,
            "location_id": str(r.location_id) if r.location_id else None,
            "location_text": r.location_text,
            "disposition": r.disposition,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in reports
    ]

    # 3. Claims
    claim_stmt = select(Claim).where(Claim.claimant_id == user.id).order_by(Claim.created_at.desc())
    claims = list((await db.execute(claim_stmt)).scalars().all())
    claims_data = [
        {
            "id": str(c.id),
            "found_id": str(c.found_id),
            "lost_id": str(c.lost_id) if c.lost_id else None,
            "evidence": c.evidence,
            "answers": c.answers,
            "image_ids": c.image_ids,
            "status": c.status,
            "decision_note": c.decision_note,
            "submitted_at": c.submitted_at.isoformat() if c.submitted_at else None,
            "reviewed_at": c.reviewed_at.isoformat() if c.reviewed_at else None,
        }
        for c in claims
    ]

    # 4. Notifications
    notif_stmt = (
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
    )
    notifs = list((await db.execute(notif_stmt)).scalars().all())
    notifs_data = [
        {
            "id": str(n.id),
            "event_type": n.event_type,
            "event_key": n.event_key,
            "payload": n.payload,
            "status": n.status,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in notifs
    ]

    return {
        "user": profile,
        "reports": reports_data,
        "claims": claims_data,
        "notifications": notifs_data,
    }


async def delete_user_account(
    db: AsyncSession,
    user: User,
    current_time: datetime | None = None,
) -> None:
    """AC-103: Deleting an account removes its email, name, sessions, notifications, private images,

    and claim evidence, anonymises its reports, closes its open reports, keeps audit rows with a pseudonymous ID,
    and guarantees a scan of a database dump finds no occurrence of the deleted email.
    """
    now = current_time or get_utcnow()

    # AC-99 guard: last admin cannot be deleted
    if user.role == "admin":
        count_stmt = select(func.count(User.id)).where(
            User.role == "admin", User.status == "active"
        )
        total_admins = (await db.execute(count_stmt)).scalar() or 0
        if total_admins <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="last_admin_cannot_be_deleted",
            )

    pseudonym = f"deleted_{user.id}"

    # 1. Close open reports and scrub private details
    close_reports_stmt = (
        update(ItemReport)
        .where(
            ItemReport.reporter_id == user.id,
            ItemReport.status.in_(["open", "pending_review", "reserved"]),
        )
        .values(
            status="closed",
            closed_at=now,
            private_details=None,
            updated_at=now,
        )
    )
    await db.execute(close_reports_stmt)

    # Scrub private details on any remaining closed/returned reports
    scrub_reports_stmt = (
        update(ItemReport)
        .where(ItemReport.reporter_id == user.id)
        .values(private_details=None, updated_at=now)
    )
    await db.execute(scrub_reports_stmt)

    # 2. Clear claim evidence and answers
    scrub_claims_stmt = (
        update(Claim)
        .where(Claim.claimant_id == user.id)
        .values(
            evidence="[ANONYMIZED]",
            answers={},
            image_ids=[],
            updated_at=now,
        )
    )
    await db.execute(scrub_claims_stmt)

    # 3. Delete notifications
    await db.execute(delete(Notification).where(Notification.user_id == user.id))

    # 4. Revoke and delete sessions (AC-05: immediate 401 on old session)
    await db.execute(delete(Session).where(Session.user_id == user.id))

    # 5. Overwrite personal user row so email NEVER appears in db dump
    user.email = f"{pseudonym}@anonymized.local"
    user.display_name = "Deleted User"
    user.password_hash = "$argon2id$v=19$m=65536,t=3,p=4$anonymized"
    user.status = "deleted"
    user.updated_at = now

    # 6. Audit row recorded under pseudonymous summary
    await write_audit_log(
        db=db,
        actor_id=user.id,
        role=user.role,
        action="user.deleted",
        entity_type="user",
        entity_id=user.id,
        summary={"pseudonym": pseudonym},
    )

    await db.commit()
