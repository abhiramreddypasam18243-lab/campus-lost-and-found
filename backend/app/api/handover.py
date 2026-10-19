"""Handover desk API endpoints for code verification, status, reissue, and expiry (AC-90 to AC-96)."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_role, verify_csrf
from app.core.database import get_db
from app.models.user import User
from app.schemas.handover import (
    HandoverReissueRequest,
    HandoverStatusResponse,
    HandoverVerificationRequest,
    HandoverVerifyResponse,
)
from app.services import handover as handover_service

router = APIRouter(prefix="/api/mod/handovers", tags=["handovers"])


@router.get(
    "/{claim_id}",
    response_model=HandoverStatusResponse,
)
async def get_handover_status(
    claim_id: uuid.UUID,
    current_user: User = Depends(require_role("moderator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> HandoverStatusResponse:
    """AC-96: Desk view showing attempts left and lock status. NEVER reveals code or HMAC."""
    return await handover_service.get_handover_desk_status(db, claim_id, current_user)


@router.post(
    "/{claim_id}/verify",
    response_model=HandoverVerifyResponse,
    dependencies=[Depends(verify_csrf)],
)
async def verify_handover(
    claim_id: uuid.UUID,
    payload: HandoverVerificationRequest,
    current_user: User = Depends(require_role("moderator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> HandoverVerifyResponse:
    """AC-90, AC-91, AC-93, AC-95: Verify claimant code at desk and complete handover atomically."""
    return await handover_service.verify_and_complete_handover(
        db=db,
        claim_id=claim_id,
        raw_code=payload.code,
        identity_note=payload.identity_note,
        moderator=current_user,
    )


@router.post(
    "/{claim_id}/reissue",
    response_model=dict[str, str],
    dependencies=[Depends(verify_csrf)],
)
async def reissue_handover(
    claim_id: uuid.UUID,
    payload: HandoverReissueRequest,
    current_user: User = Depends(require_role("moderator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """AC-92: Moderator reissues code (max 3 times), resets attempts and 48h clock."""
    await handover_service.reissue_handover(
        db=db,
        claim_id=claim_id,
        moderator=current_user,
        reason=payload.reason,
    )
    return {"status": "reissued", "message": "New handover code issued and sent to claimant."}


@router.post(
    "/expire",
    response_model=dict[str, int],
    dependencies=[Depends(verify_csrf)],
)
async def expire_handovers(
    current_user: User = Depends(require_role("moderator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """AC-94: Sweep and expire stale handovers."""
    expired_count = await handover_service.expire_stale_handovers(db)
    return {"expired_count": expired_count}
