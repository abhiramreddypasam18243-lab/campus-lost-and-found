"""Service layer for handover codes, verification, reissue, and completion (AC-86 to AC-96)."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.domain.claims import transition_claim
from app.domain.handover import (
    can_attempt_verification,
    can_reissue_code,
    compute_code_hmac,
    generate_handover_code,
    is_code_valid_at_time,
    normalize_handover_code,
    verify_code_constant_time,
)
from app.models.claims import Claim
from app.models.handover import Handover
from app.models.report import ItemReport
from app.models.user import User
from app.schemas.handover import (
    HandoverDeskItem,
    HandoverStatusResponse,
    HandoverVerifyResponse,
)
from app.services.audit import write_audit_log
from app.services.notification import create_notification


def get_utcnow() -> datetime:
    return datetime.now(UTC)


def get_handover_secret() -> str:
    return get_settings().SECRET_KEY


async def issue_handover(
    db: AsyncSession,
    claim: Claim,
    moderator: User,
    current_time: datetime | None = None,
) -> str:
    """AC-86, AC-87, AC-89: Generate an 8-character handover code, store strictly HMAC-SHA-256,

    set 48-hour expiration, and return plaintext code for the claimant.
    """
    now = current_time or get_utcnow()
    secret = get_handover_secret()

    # Generate secure random code and compute HMAC
    plaintext_code = generate_handover_code()
    normalized = normalize_handover_code(plaintext_code)
    code_hmac = compute_code_hmac(secret, normalized)

    # Check if handover record already exists (e.g. reissue or existing)
    stmt = select(Handover).where(Handover.claim_id == claim.id)
    handover = (await db.execute(stmt)).scalar_one_or_none()

    if handover is None:
        handover = Handover(
            claim_id=claim.id,
            code_hmac=code_hmac,
            attempts=0,
            max_attempts=5,
            reissue_count=0,
            max_reissues=3,
            status="issued",
            issued_at=now,
            expires_at=now + timedelta(hours=48),
            created_at=now,
            updated_at=now,
        )
        db.add(handover)
    else:
        handover.code_hmac = code_hmac
        handover.attempts = 0
        handover.status = "issued"
        handover.issued_at = now
        handover.expires_at = now + timedelta(hours=48)
        handover.updated_at = now

    await db.flush()

    found_report = await db.get(ItemReport, claim.found_id)
    found_title = found_report.title if found_report else "Item"

    # AC-71: Single-use handover code appears in in-app message and email to approved claimant
    await create_notification(
        db=db,
        user_id=claim.claimant_id,
        event_type="handover_ready",
        event_key=f"handover_code:{claim.id}:{handover.reissue_count}",
        payload={
            "found_title": found_title,
            "is_claimant": True,
            "handover_code": plaintext_code,
            "claim_id": str(claim.id),
        },
    )

    await write_audit_log(
        db=db,
        actor_id=moderator.id,
        role=moderator.role,
        action="handover.issued",
        entity_type="handover",
        entity_id=handover.id,
        summary={"claim_id": str(claim.id), "reissue_count": handover.reissue_count},
    )

    return plaintext_code


async def reissue_handover(
    db: AsyncSession,
    claim_id: uuid.UUID,
    moderator: User,
    reason: str,
    current_time: datetime | None = None,
) -> str:
    """AC-92: Moderator reissues code (at most 3 reissues), resets attempts and 48h clock."""
    now = current_time or get_utcnow()

    if moderator.role not in ("moderator", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="forbidden",
        )

    if len(reason.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="reissue_reason_too_short",
        )

    stmt = select(Handover).where(Handover.claim_id == claim_id)
    handover = (await db.execute(stmt)).scalar_one_or_none()
    if not handover:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Handover not found",
        )

    claim = await db.get(Claim, claim_id)
    if not claim or claim.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="claim_not_in_approved_state",
        )

    if not can_reissue_code(handover.reissue_count, handover.max_reissues):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="reissue_limit_exceeded",
        )

    secret = get_handover_secret()
    new_code = generate_handover_code()
    normalized = normalize_handover_code(new_code)
    new_hmac = compute_code_hmac(secret, normalized)

    handover.code_hmac = new_hmac
    handover.attempts = 0
    handover.reissue_count += 1
    handover.status = "issued"
    handover.issued_at = now
    handover.expires_at = now + timedelta(hours=48)
    handover.updated_at = now

    found_report = await db.get(ItemReport, claim.found_id)
    found_title = found_report.title if found_report else "Item"

    await create_notification(
        db=db,
        user_id=claim.claimant_id,
        event_type="handover_ready",
        event_key=f"handover_code:{claim.id}:{handover.reissue_count}",
        payload={
            "found_title": found_title,
            "is_claimant": True,
            "handover_code": new_code,
            "claim_id": str(claim.id),
        },
    )

    await write_audit_log(
        db=db,
        actor_id=moderator.id,
        role=moderator.role,
        action="handover.reissued",
        entity_type="handover",
        entity_id=handover.id,
        summary={
            "claim_id": str(claim.id),
            "reissue_count": handover.reissue_count,
            "reason": reason,
        },
    )

    await db.commit()
    await db.refresh(handover)
    return new_code


async def get_handover_desk_status(
    db: AsyncSession,
    claim_id: uuid.UUID,
    user: User,
    current_time: datetime | None = None,
) -> HandoverStatusResponse:
    """AC-96: Desk view shows attempts left and lock status. NEVER reveals code or HMAC."""
    now = current_time or get_utcnow()

    if user.role not in ("moderator", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="forbidden",
        )

    stmt = select(Handover).where(Handover.claim_id == claim_id)
    handover = (await db.execute(stmt)).scalar_one_or_none()
    if not handover:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Handover not found",
        )

    is_expired = not is_code_valid_at_time(handover.issued_at, now)
    is_locked = handover.attempts >= handover.max_attempts or handover.status == "locked"
    attempts_left = max(0, handover.max_attempts - handover.attempts)

    return HandoverStatusResponse(
        claim_id=handover.claim_id,
        status=handover.status,
        attempts=handover.attempts,
        max_attempts=handover.max_attempts,
        attempts_left=attempts_left,
        reissue_count=handover.reissue_count,
        max_reissues=handover.max_reissues,
        issued_at=handover.issued_at,
        expires_at=handover.expires_at,
        is_expired=is_expired,
        is_locked=is_locked,
    )


async def verify_and_complete_handover(
    db: AsyncSession,
    claim_id: uuid.UUID,
    raw_code: str,
    identity_note: str,
    moderator: User,
    current_time: datetime | None = None,
) -> HandoverVerifyResponse:
    """AC-90, AC-91, AC-93, AC-95: Constant-time code verification and atomic completion transaction."""
    now = current_time or get_utcnow()

    if moderator.role not in ("moderator", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="forbidden",
        )

    # AC-93: Identity check note required (at least 10 chars)
    if len(identity_note.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="identity_note_too_short",
        )

    stmt = select(Handover).where(Handover.claim_id == claim_id)
    handover = (await db.execute(stmt)).scalar_one_or_none()
    if not handover:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Handover not found",
        )

    # AC-90: Verifying the same code again returns 409 code_used
    if handover.status == "verified":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="code_used",
        )

    # AC-91: Handover locks after 5 wrong attempts; 6th attempt returns 423 handover_locked
    if (
        not can_attempt_verification(handover.attempts, handover.max_attempts)
        or handover.status == "locked"
    ):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="handover_locked",
        )

    # AC-89: Expiration check
    if not is_code_valid_at_time(handover.issued_at, now):
        handover.status = "expired"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="code_expired",
        )

    secret = get_handover_secret()
    is_match = verify_code_constant_time(secret, raw_code, handover.code_hmac)

    if not is_match:
        handover.attempts += 1
        if handover.attempts >= handover.max_attempts:
            handover.status = "locked"
            await write_audit_log(
                db=db,
                actor_id=moderator.id,
                role=moderator.role,
                action="handover.locked",
                entity_type="handover",
                entity_id=handover.id,
                summary={"claim_id": str(claim_id)},
            )
        await db.commit()
        attempts_left = max(0, handover.max_attempts - handover.attempts)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_code",
                "message": "Invalid handover code.",
                "attempts_left": attempts_left,
            },
        )

    # SUCCESS: Execute single atomic transaction per AC-93
    claim = await db.get(Claim, claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    found_report = await db.get(ItemReport, claim.found_id)
    if not found_report:
        raise HTTPException(status_code=404, detail="Found report not found")

    # 1. Update handover
    handover.status = "verified"
    handover.verified_at = now
    handover.verified_by_id = moderator.id
    handover.identity_note = identity_note
    handover.updated_at = now

    # 2. Complete claim
    claim.status = transition_claim(claim.status, "complete")
    claim.reviewed_at = now
    claim.updated_at = now

    # 3. Found report -> returned
    found_report.status = "returned"
    found_report.updated_at = now

    # 4. Linked lost report -> resolved (if present)
    if claim.lost_id:
        lost_report = await db.get(ItemReport, claim.lost_id)
        if lost_report and lost_report.status == "open":
            lost_report.status = "resolved"
            lost_report.updated_at = now

    # 5. Reject other open claims on this found item with 'item_returned'
    other_claims_stmt = (
        update(Claim)
        .where(
            Claim.found_id == claim.found_id,
            Claim.id != claim.id,
            Claim.status.in_(["submitted", "under_review", "needs_more_info"]),
        )
        .values(
            status="rejected",
            decision_note="item_returned",
            reviewer_id=moderator.id,
            reviewed_at=now,
            updated_at=now,
        )
    )
    await db.execute(other_claims_stmt)

    # 6. Write audit logs
    await write_audit_log(
        db=db,
        actor_id=moderator.id,
        role=moderator.role,
        action="handover.completed",
        entity_type="handover",
        entity_id=handover.id,
        summary={
            "claim_id": str(claim.id),
            "found_id": str(found_report.id),
            "identity_note": identity_note,
        },
    )

    # 7. Notifications
    await create_notification(
        db=db,
        user_id=claim.claimant_id,
        event_type="claim_update",
        event_key=f"handover_completed:{claim.id}",
        payload={"found_title": found_report.title, "claim_status": "completed"},
    )
    await create_notification(
        db=db,
        user_id=found_report.reporter_id,
        event_type="claim_update",
        event_key=f"item_returned:{found_report.id}",
        payload={"found_title": found_report.title, "claim_status": "returned"},
    )

    await db.commit()
    await db.refresh(handover)
    await db.refresh(claim)

    return HandoverVerifyResponse(
        success=True,
        claim_id=claim.id,
        found_id=found_report.id,
        status="completed",
        message="Handover successfully verified and completed.",
    )


async def expire_stale_handovers(db: AsyncSession, current_time: datetime | None = None) -> int:
    """AC-94: When a code expires unused, the claim becomes expired and found item returns to open."""
    now = current_time or get_utcnow()

    stmt = select(Handover).where(
        Handover.status == "issued",
        Handover.expires_at <= now,
    )
    res = await db.execute(stmt)
    stale_handovers = res.scalars().all()

    count = 0
    for handover in stale_handovers:
        handover.status = "expired"
        handover.updated_at = now

        claim = await db.get(Claim, handover.claim_id)
        if claim and claim.status == "approved":
            claim.status = transition_claim(claim.status, "expire")
            claim.updated_at = now

            found_report = await db.get(ItemReport, claim.found_id)
            if found_report and found_report.status == "reserved":
                found_report.status = "open"
                found_report.updated_at = now

            await create_notification(
                db=db,
                user_id=claim.claimant_id,
                event_type="claim_update",
                event_key=f"handover_expired:{claim.id}",
                payload={
                    "found_title": found_report.title if found_report else "Item",
                    "claim_status": "expired",
                },
            )

            await write_audit_log(
                db=db,
                actor_id=None,
                role="system",
                action="handover.expired",
                entity_type="handover",
                entity_id=handover.id,
                summary={"claim_id": str(claim.id)},
            )
            count += 1

    if count > 0:
        await db.commit()
    return count


async def list_desk_handovers(
    db: AsyncSession, current_time: datetime | None = None
) -> list[HandoverDeskItem]:
    """Handovers waiting at the desk (issued or locked), soonest expiry first."""
    now = current_time or get_utcnow()
    stmt = (
        select(Handover, Claim.found_id, ItemReport.title)
        .join(Claim, Claim.id == Handover.claim_id)
        .join(ItemReport, ItemReport.id == Claim.found_id)
        .where(Handover.status.in_(["issued", "locked"]))
        .order_by(Handover.expires_at.asc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        HandoverDeskItem(
            claim_id=h.claim_id,
            found_id=found_id,
            found_title=title,
            status=h.status,
            attempts_left=max(0, h.max_attempts - h.attempts),
            expires_at=h.expires_at,
            is_expired=not is_code_valid_at_time(h.issued_at, now),
            is_locked=h.attempts >= h.max_attempts or h.status == "locked",
        )
        for h, found_id, title in rows
    ]
