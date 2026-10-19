"""Moderation API endpoints for queue management, claim locks, and decisions (AC-78 to AC-85)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.claims import to_claim_response
from app.core.auth import require_role, verify_csrf
from app.core.database import get_db
from app.models.user import User
from app.schemas.claims import (
    ClaimDecisionRequest,
    ClaimResponse,
    ModeratorQueueResponse,
)
from app.services import claims as claim_service

router = APIRouter(prefix="/api/mod", tags=["moderation"])


@router.get(
    "/queue",
    response_model=ModeratorQueueResponse,
)
async def get_moderation_queue(
    current_user: User = Depends(require_role("moderator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> ModeratorQueueResponse:
    """AC-78, AC-84, AC-85: Unified moderation queue with locks, escalation, and claimant flags."""
    items = await claim_service.get_moderator_queue(db, current_user)
    return ModeratorQueueResponse(items=items, total=len(items))


@router.post(
    "/claims/{claim_id}/open",
    response_model=ClaimResponse,
    dependencies=[Depends(verify_csrf)],
)
async def open_claim(
    claim_id: uuid.UUID,
    current_user: User = Depends(require_role("moderator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> ClaimResponse:
    """AC-78: Open a claim and acquire exclusive 30-minute review lock."""
    claim = await claim_service.open_claim_lock(db, claim_id, current_user)
    return to_claim_response(claim)


@router.post(
    "/claims/{claim_id}/approve",
    response_model=ClaimResponse,
    dependencies=[Depends(verify_csrf)],
)
async def approve_claim(
    claim_id: uuid.UUID,
    payload: ClaimDecisionRequest,
    current_user: User = Depends(require_role("moderator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> ClaimResponse:
    """AC-79, AC-80, AC-81: Approve claim, reserve found item, create notification."""
    claim = await claim_service.decide_claim(
        db, claim_id, current_user, "approve", payload.decision_note
    )
    return to_claim_response(claim)


@router.post(
    "/claims/{claim_id}/reject",
    response_model=ClaimResponse,
    dependencies=[Depends(verify_csrf)],
)
async def reject_claim(
    claim_id: uuid.UUID,
    payload: ClaimDecisionRequest,
    current_user: User = Depends(require_role("moderator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> ClaimResponse:
    """AC-79, AC-80: Reject claim with decision note and notify claimant."""
    claim = await claim_service.decide_claim(
        db, claim_id, current_user, "reject", payload.decision_note
    )
    return to_claim_response(claim)


@router.post(
    "/claims/{claim_id}/request-info",
    response_model=ClaimResponse,
    dependencies=[Depends(verify_csrf)],
)
async def request_info_claim(
    claim_id: uuid.UUID,
    payload: ClaimDecisionRequest,
    current_user: User = Depends(require_role("moderator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> ClaimResponse:
    """AC-79, AC-82: Request more info, transition to needs_more_info and release lock."""
    claim = await claim_service.decide_claim(
        db, claim_id, current_user, "request_info", payload.decision_note
    )
    return to_claim_response(claim)


class ReportDispositionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disposition: str


@router.post(
    "/reports/{report_id}/approve",
    dependencies=[Depends(verify_csrf)],
)
async def approve_report(
    report_id: uuid.UUID,
    current_user: User = Depends(require_role("moderator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Approve a pending report, transitioning it to open (AC-22, AC-25)."""
    from datetime import UTC, datetime

    from app.models.report import ItemReport
    from app.services.audit import write_audit_log

    report = await db.get(ItemReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="report_not_found")
    if report.status != "pending_review":
        raise HTTPException(status_code=409, detail="invalid_transition")

    now = datetime.now(UTC)
    report.status = "open"
    report.reviewed_by = current_user.id
    report.updated_at = now

    await write_audit_log(
        db=db,
        actor_id=current_user.id,
        role=current_user.role,
        action="report.approved",
        entity_type="item_report",
        entity_id=report.id,
    )
    await db.commit()
    return {"status": "open", "message": "Report approved and listed."}


@router.post(
    "/reports/{report_id}/remove",
    dependencies=[Depends(verify_csrf)],
)
async def remove_report(
    report_id: uuid.UUID,
    current_user: User = Depends(require_role("moderator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Moderator removes report (AC-25, AC-98)."""
    from datetime import UTC, datetime

    from app.models.report import ItemReport
    from app.services.audit import write_audit_log

    report = await db.get(ItemReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="report_not_found")

    now = datetime.now(UTC)
    report.status = "removed"
    report.closed_at = now
    report.reviewed_by = current_user.id
    report.updated_at = now

    await write_audit_log(
        db=db,
        actor_id=current_user.id,
        role=current_user.role,
        action="report.removed",
        entity_type="item_report",
        entity_id=report.id,
    )
    await db.commit()
    return {"status": "removed", "message": "Report removed."}


@router.post(
    "/reports/{report_id}/disposition",
    dependencies=[Depends(verify_csrf)],
)
async def record_disposition(
    report_id: uuid.UUID,
    payload: ReportDispositionRequest,
    current_user: User = Depends(require_role("moderator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """AC-100: Record disposition ('donated', 'disposed', 'kept') on unclaimed_expired report."""
    from app.services.retention import record_report_disposition

    report = await record_report_disposition(
        db=db,
        report_id=report_id,
        disposition=payload.disposition,
        moderator=current_user,
    )
    return {"id": str(report.id), "disposition": report.disposition or "", "status": report.status}
