"""Claim API endpoints for submitting, viewing, updating, and withdrawing claims (AC-75, AC-77, AC-82, AC-83)."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_authenticated_user, require_verified_user, verify_csrf
from app.core.database import get_db
from app.domain.claims import is_claim_escalated
from app.models.claims import Claim
from app.models.notifications import Notification
from app.models.report import ItemReport
from app.models.user import User
from app.schemas.claims import ClaimCreate, ClaimEvidenceUpdate, ClaimResponse
from app.services import claims as claim_service

router = APIRouter(prefix="/api/claims", tags=["claims"])


def to_claim_response(
    claim: Claim, handover_code: str | None = None, found_title: str | None = None
) -> ClaimResponse:
    now = datetime.now(UTC)
    escalated = is_claim_escalated(claim.submitted_at, now, claim.status)
    return ClaimResponse(
        id=claim.id,
        found_id=claim.found_id,
        lost_id=claim.lost_id,
        claimant_id=claim.claimant_id,
        evidence=claim.evidence,
        answers=claim.answers,
        image_ids=claim.image_ids,
        status=claim.status,
        decision_note=claim.decision_note,
        reviewer_id=claim.reviewer_id,
        locked_by_id=claim.locked_by_id,
        lock_expires_at=claim.lock_expires_at,
        submitted_at=claim.submitted_at,
        reviewed_at=claim.reviewed_at,
        escalated=escalated,
        handover_code=handover_code,
        found_title=found_title,
        created_at=claim.created_at,
    )


async def _found_titles(db: AsyncSession, found_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    """Titles of the claimed items (public field), so a claimant can tell claims apart."""
    if not found_ids:
        return {}
    rows = await db.execute(
        select(ItemReport.id, ItemReport.title).where(ItemReport.id.in_(found_ids))
    )
    return {rid: title for rid, title in rows.all()}


@router.post(
    "",
    response_model=ClaimResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_csrf)],
)
async def submit_claim(
    payload: ClaimCreate,
    current_user: User = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
) -> ClaimResponse:
    """AC-75: Submit a claim on a found item with prompt answers and evidence."""
    claim = await claim_service.create_claim(db, current_user, payload)
    return to_claim_response(claim)


@router.get(
    "/my",
    response_model=list[ClaimResponse],
)
async def list_my_claims(
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> list[ClaimResponse]:
    """List claims submitted by the current user."""
    stmt = (
        select(Claim).where(Claim.claimant_id == current_user.id).order_by(Claim.created_at.desc())
    )
    result = await db.execute(stmt)
    claims = result.scalars().all()

    # Pre-fetch handover codes for any approved or completed claims
    notif_stmt = (
        select(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.event_type == "handover_ready",
        )
        .order_by(Notification.created_at.desc())
    )
    notifs = (await db.execute(notif_stmt)).scalars().all()
    claim_code_map: dict[str, str] = {}
    for notif in notifs:
        cid = notif.payload.get("claim_id")
        code = notif.payload.get("handover_code")
        if cid and code and cid not in claim_code_map:
            claim_code_map[cid] = code

    titles = await _found_titles(db, [c.found_id for c in claims])
    return [
        to_claim_response(
            c, handover_code=claim_code_map.get(str(c.id)), found_title=titles.get(c.found_id)
        )
        for c in claims
    ]


@router.get(
    "/{claim_id}",
    response_model=ClaimResponse,
)
async def get_claim(
    claim_id: uuid.UUID,
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> ClaimResponse:
    """AC-77, AC-96: View claim detail. Allowed only for claimant and moderators (404 otherwise).

    Claimant receives their single-use handover code; moderators and others never receive code or HMAC.
    """
    claim = await claim_service.get_claim_detail(db, claim_id, current_user)
    handover_code = None
    if current_user.id == claim.claimant_id and claim.status in ("approved", "completed"):
        stmt = (
            select(Notification)
            .where(
                Notification.user_id == current_user.id,
                Notification.event_type == "handover_ready",
            )
            .order_by(Notification.created_at.desc())
        )
        notifs = (await db.execute(stmt)).scalars().all()
        for notif in notifs:
            if notif.payload.get("claim_id") == str(claim.id):
                handover_code = notif.payload.get("handover_code")
                break
    titles = await _found_titles(db, [claim.found_id])
    return to_claim_response(
        claim, handover_code=handover_code, found_title=titles.get(claim.found_id)
    )


@router.post(
    "/{claim_id}/withdraw",
    response_model=ClaimResponse,
    dependencies=[Depends(verify_csrf)],
)
async def withdraw_claim(
    claim_id: uuid.UUID,
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> ClaimResponse:
    """AC-83: Withdraw a claim."""
    claim = await claim_service.withdraw_claim(db, claim_id, current_user)
    return to_claim_response(claim)


@router.patch(
    "/{claim_id}/evidence",
    response_model=ClaimResponse,
    dependencies=[Depends(verify_csrf)],
)
async def update_claim_evidence(
    claim_id: uuid.UUID,
    payload: ClaimEvidenceUpdate,
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> ClaimResponse:
    """AC-82: Add evidence when info requested, returning claim to submitted."""
    claim = await claim_service.update_claim_evidence(db, claim_id, current_user, payload)
    return to_claim_response(claim)
