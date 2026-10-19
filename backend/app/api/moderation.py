"""Moderation API endpoints for queue management, claim locks, and decisions (AC-78 to AC-85)."""

import uuid

from fastapi import APIRouter, Depends
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
