"""Service layer for claims, verification, conflict-of-interest checks,

moderation queue, and locks (AC-75 to AC-85).
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.claims import (
    calculate_active_claim_limit,
    can_moderator_access_claim,
    check_conflict_of_interest,
    is_claim_escalated,
    is_lock_active,
    transition_claim,
    validate_verification_answers,
)
from app.models.claims import Claim
from app.models.report import ItemImage, ItemReport
from app.models.user import User
from app.schemas.claims import ClaimCreate, ClaimEvidenceUpdate, ModeratorQueueItem
from app.services.audit import write_audit_log
from app.services.notification import create_notification


def get_utcnow() -> datetime:
    return datetime.now(UTC)


async def get_user_rejected_claims_30d(
    db: AsyncSession, claimant_id: uuid.UUID, cutoff: datetime
) -> int:
    """Count claims rejected for claimant in the last 30 days (AC-84)."""
    stmt = select(func.count(Claim.id)).where(
        Claim.claimant_id == claimant_id,
        Claim.status == "rejected",
        Claim.reviewed_at >= cutoff,
    )
    result = await db.execute(stmt)
    return int(result.scalar() or 0)


async def get_user_active_claims_count(db: AsyncSession, claimant_id: uuid.UUID) -> int:
    """Count currently active claims for claimant."""
    stmt = select(func.count(Claim.id)).where(
        Claim.claimant_id == claimant_id,
        Claim.status.in_(["submitted", "under_review", "needs_more_info", "approved"]),
    )
    result = await db.execute(stmt)
    return int(result.scalar() or 0)


async def create_claim(
    db: AsyncSession,
    claimant: User,
    payload: ClaimCreate,
    current_time: datetime | None = None,
) -> Claim:
    """AC-75: Create a new claim on a found item with prompt answers and evidence."""
    now = current_time or get_utcnow()

    # AC-02: User must be verified
    if not claimant.email_verified_at:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="email_not_verified",
        )

    # Found report lookup
    found_report = await db.get(ItemReport, payload.found_id)
    if not found_report or found_report.type != "found":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Found report not found",
        )

    # Check status of found report
    if found_report.status == "reserved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="item_already_reserved",
        )
    if found_report.status != "open":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="item_not_open_for_claims",
        )

    # Conflict of interest: Cannot claim own found report (AC-75, AC-80)
    if found_report.reporter_id == claimant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="cannot_claim_own_report",
        )

    # AC-75: At most one claim per found item per user
    existing_claim_stmt = select(Claim).where(
        Claim.found_id == payload.found_id,
        Claim.claimant_id == claimant.id,
        Claim.status.in_(["submitted", "under_review", "needs_more_info", "approved"]),
    )
    existing_claim = (await db.execute(existing_claim_stmt)).scalar_one_or_none()
    if existing_claim:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="duplicate_claim_for_item",
        )

    # AC-75: Validate prompt answers
    prompts = found_report.verification_prompts or []
    ok, err = validate_verification_answers(prompts, payload.answers)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=err or "missing_verification_answers",
        )

    # AC-84: Abuse protection - limit active claims if 3 rejected in last 30d
    cutoff_30d = now - timedelta(days=30)
    rejected_30d = await get_user_rejected_claims_30d(db, claimant.id, cutoff_30d)
    max_active = calculate_active_claim_limit(rejected_30d)
    active_count = await get_user_active_claims_count(db, claimant.id)

    if active_count >= max_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="claim_limit_exceeded",
        )

    # Create Claim
    claim = Claim(
        found_id=payload.found_id,
        lost_id=payload.lost_id,
        claimant_id=claimant.id,
        evidence=payload.evidence,
        answers=payload.answers,
        image_ids=[str(img_id) for img_id in payload.image_ids],
        status="submitted",
        submitted_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(claim)
    await db.flush()

    await write_audit_log(
        db=db,
        actor_id=claimant.id,
        role=claimant.role,
        action="claim.created",
        entity_type="claim",
        entity_id=claim.id,
        summary={"found_id": str(payload.found_id)},
    )
    await db.commit()
    await db.refresh(claim)
    return claim


async def get_claim_detail(
    db: AsyncSession,
    claim_id: uuid.UUID,
    user: User,
    current_time: datetime | None = None,
) -> Claim:
    """AC-09, AC-77: Claim evidence and answers are visible only to claimant and moderators."""
    claim = await db.get(Claim, claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Claim not found",
        )

    # Non-mod, non-claimant gets 404 (anti-enumeration)
    if user.role not in ("moderator", "admin") and claim.claimant_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Claim not found",
        )

    return claim


async def withdraw_claim(
    db: AsyncSession,
    claim_id: uuid.UUID,
    user: User,
    current_time: datetime | None = None,
) -> Claim:
    """AC-83: Claimant withdraws claim.

    If withdrawing after approval, returns found item to 'open'.
    """
    now = current_time or get_utcnow()
    claim = await db.get(Claim, claim_id)
    if not claim or claim.claimant_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Claim not found",
        )

    was_approved = claim.status == "approved"
    try:
        new_status = transition_claim(claim.status, "withdraw")
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="invalid_transition",
        ) from err

    claim.status = new_status
    claim.locked_by_id = None
    claim.lock_expires_at = None
    claim.updated_at = now

    # If was approved, revert found item to 'open' (AC-83)
    if was_approved:
        found_report = await db.get(ItemReport, claim.found_id)
        if found_report and found_report.status == "reserved":
            found_report.status = "open"
            found_report.updated_at = now

    await write_audit_log(
        db=db,
        actor_id=user.id,
        role=user.role,
        action="claim.withdrawn",
        entity_type="claim",
        entity_id=claim.id,
        summary={"was_approved": was_approved},
    )
    await db.commit()
    await db.refresh(claim)
    return claim


async def update_claim_evidence(
    db: AsyncSession,
    claim_id: uuid.UUID,
    user: User,
    payload: ClaimEvidenceUpdate,
    current_time: datetime | None = None,
) -> Claim:
    """AC-82: needs_more_info lets claimant add evidence and resubmit."""
    now = current_time or get_utcnow()
    claim = await db.get(Claim, claim_id)
    if not claim or claim.claimant_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Claim not found",
        )

    try:
        new_status = transition_claim(claim.status, "submit_info")
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="invalid_transition",
        ) from err

    claim.evidence = payload.evidence
    if payload.answers is not None:
        claim.answers = payload.answers
    if payload.image_ids is not None:
        claim.image_ids = [str(x) for x in payload.image_ids]

    claim.status = new_status
    claim.submitted_at = now  # resets queue time
    claim.updated_at = now

    await write_audit_log(
        db=db,
        actor_id=user.id,
        role=user.role,
        action="claim.resubmitted",
        entity_type="claim",
        entity_id=claim.id,
        summary={},
    )
    await db.commit()
    await db.refresh(claim)
    return claim


async def open_claim_lock(
    db: AsyncSession,
    claim_id: uuid.UUID,
    moderator: User,
    current_time: datetime | None = None,
) -> Claim:
    """AC-78: Opening a claim assigns a lock for 30 minutes."""
    now = current_time or get_utcnow()
    if moderator.role not in ("moderator", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="forbidden",
        )

    claim = await db.get(Claim, claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Claim not found",
        )

    # Check lock conflict
    if not can_moderator_access_claim(moderator.id, claim.locked_by_id, claim.lock_expires_at, now):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="claim_locked",
        )

    # If submitted, transition to under_review
    if claim.status == "submitted":
        claim.status = transition_claim("submitted", "open_review")

    claim.locked_by_id = moderator.id
    claim.lock_expires_at = now + timedelta(minutes=30)
    claim.updated_at = now

    await write_audit_log(
        db=db,
        actor_id=moderator.id,
        role=moderator.role,
        action="claim.locked",
        entity_type="claim",
        entity_id=claim.id,
        summary={
            "lock_expires_at": claim.lock_expires_at.isoformat() if claim.lock_expires_at else None
        },
    )
    await db.commit()
    await db.refresh(claim)
    return claim


async def decide_claim(
    db: AsyncSession,
    claim_id: uuid.UUID,
    moderator: User,
    action: str,
    decision_note: str,
    current_time: datetime | None = None,
) -> Claim:
    """AC-78, AC-79, AC-80, AC-81: Moderator approves, rejects, or requests info with decision note."""
    now = current_time or get_utcnow()

    if moderator.role not in ("moderator", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="forbidden",
        )

    if len(decision_note.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="decision_note_too_short",
        )

    claim = await db.get(Claim, claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Claim not found",
        )

    found_report = await db.get(ItemReport, claim.found_id)
    if not found_report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Found report not found",
        )

    # AC-80: Conflict of interest
    if check_conflict_of_interest(moderator.id, found_report.reporter_id, claim.claimant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="conflict_of_interest",
        )

    # AC-78: Lock check
    if not can_moderator_access_claim(moderator.id, claim.locked_by_id, claim.lock_expires_at, now):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="claim_locked",
        )

    # Check legal transition
    try:
        new_status = transition_claim(claim.status, action)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="invalid_transition",
        ) from err

    if action == "approve":
        # AC-81: Only one claim per found item can be approved at a time
        if found_report.status == "reserved":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="item_already_reserved",
            )
        found_report.status = "reserved"
        found_report.updated_at = now

        claim.status = new_status
        claim.decision_note = decision_note
        claim.reviewer_id = moderator.id
        claim.reviewed_at = now
        claim.locked_by_id = None
        claim.lock_expires_at = None
        claim.updated_at = now

        await write_audit_log(
            db=db,
            actor_id=moderator.id,
            role=moderator.role,
            action="claim.approved",
            entity_type="claim",
            entity_id=claim.id,
            summary={"found_id": str(found_report.id)},
        )
        await create_notification(
            db=db,
            user_id=claim.claimant_id,
            event_type="claim_update",
            event_key=f"claim_approved:{claim.id}",
            payload={"found_title": found_report.title, "claim_status": "approved"},
        )

        # AC-79: Approving makes item reserved and issues a handover
        from app.services.handover import issue_handover

        await issue_handover(db, claim, moderator, now)

    elif action == "reject":
        claim.status = new_status
        claim.decision_note = decision_note
        claim.reviewer_id = moderator.id
        claim.reviewed_at = now
        claim.locked_by_id = None
        claim.lock_expires_at = None
        claim.updated_at = now

        await write_audit_log(
            db=db,
            actor_id=moderator.id,
            role=moderator.role,
            action="claim.rejected",
            entity_type="claim",
            entity_id=claim.id,
            summary={"found_id": str(found_report.id)},
        )
        await create_notification(
            db=db,
            user_id=claim.claimant_id,
            event_type="claim_update",
            event_key=f"claim_rejected:{claim.id}",
            payload={"found_title": found_report.title, "claim_status": "rejected"},
        )

    elif action == "request_info":
        claim.status = new_status
        claim.decision_note = decision_note
        claim.reviewer_id = moderator.id
        claim.reviewed_at = now
        claim.locked_by_id = None
        claim.lock_expires_at = None
        claim.updated_at = now

        await write_audit_log(
            db=db,
            actor_id=moderator.id,
            role=moderator.role,
            action="claim.info_requested",
            entity_type="claim",
            entity_id=claim.id,
            summary={"found_id": str(found_report.id)},
        )
        await create_notification(
            db=db,
            user_id=claim.claimant_id,
            event_type="claim_update",
            event_key=f"claim_needs_more_info:{claim.id}",
            payload={"found_title": found_report.title, "claim_status": "needs_more_info"},
        )

    await db.commit()
    await db.refresh(claim)
    return claim


async def get_moderator_queue(
    db: AsyncSession,
    user: User,
    current_time: datetime | None = None,
) -> list[ModeratorQueueItem]:
    """AC-78, AC-84, AC-85: Moderator queue with pending reports, duplicate images,

    and claims ordered by escalated first, then submission time.
    """
    now = current_time or get_utcnow()
    if user.role not in ("moderator", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="forbidden",
        )

    items: list[ModeratorQueueItem] = []

    # 1. Active claims
    stmt_claims = (
        select(Claim, ItemReport.title)
        .join(ItemReport, Claim.found_id == ItemReport.id)
        .where(Claim.status.in_(["submitted", "under_review", "needs_more_info"]))
        .order_by(Claim.submitted_at.asc())
    )
    res_claims = (await db.execute(stmt_claims)).all()

    # Pre-fetch rejected counts for AC-84 flagged claimant check
    cutoff_30d = now - timedelta(days=30)
    for claim, found_title in res_claims:
        escalated = is_claim_escalated(claim.submitted_at, now, claim.status)
        locked = is_lock_active(claim.locked_by_id, claim.lock_expires_at, now)
        rej_count = await get_user_rejected_claims_30d(db, claim.claimant_id, cutoff_30d)

        items.append(
            ModeratorQueueItem(
                id=claim.id,
                item_type="claim",
                title=f"Claim on '{found_title}'",
                status=claim.status,
                submitted_at=claim.submitted_at,
                escalated=escalated,
                locked_by_id=claim.locked_by_id,
                lock_expires_at=claim.lock_expires_at,
                is_locked=locked,
                claimant_flagged=(rej_count >= 3),
                extra_data={
                    "found_id": str(claim.found_id),
                    "claimant_id": str(claim.claimant_id),
                },
            )
        )

    # 2. Pending reports (found reports needing review)
    stmt_reports = (
        select(ItemReport)
        .where(ItemReport.status == "pending_review")
        .order_by(ItemReport.created_at.asc())
    )
    res_reports = (await db.execute(stmt_reports)).scalars().all()
    for rep in res_reports:
        items.append(
            ModeratorQueueItem(
                id=rep.id,
                item_type="report",
                title=rep.title,
                status=rep.status,
                submitted_at=rep.created_at,
                escalated=False,
                is_locked=False,
                extra_data={"category": rep.category},
            )
        )

    # 3. Duplicate images
    stmt_dups = (
        select(ItemImage)
        .where(ItemImage.moderation_status == "flagged")
        .order_by(ItemImage.created_at.asc())
    )
    res_dups = (await db.execute(stmt_dups)).scalars().all()
    for dup in res_dups:
        items.append(
            ModeratorQueueItem(
                id=dup.id,
                item_type="duplicate_image",
                title="Duplicate Image Flagged",
                status="flagged",
                submitted_at=dup.created_at,
                escalated=False,
                is_locked=False,
                extra_data={
                    "report_id": str(dup.report_id),
                },
            )
        )

    # Sort queue: escalated claims first, then submission time ascending (AC-78, AC-85)
    items.sort(key=lambda x: (not x.escalated, x.submitted_at))
    return items
