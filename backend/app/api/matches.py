from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import require_authenticated_user, verify_csrf
from app.core.database import get_db
from app.models.matching import MatchCandidate
from app.models.report import ItemReport
from app.models.user import User
from app.schemas.found import PublicFoundItemSummary
from app.schemas.matching import MatchCandidateResponse, MatchListResponse
from app.services.location import resolve_building_for_location
from app.services.matching import dismiss_candidate

router = APIRouter(tags=["matches"])


@router.get(
    "/api/reports/{report_id}/matches",
    response_model=MatchListResponse,
)
async def get_report_matches(
    report_id: uuid.UUID,
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> MatchListResponse:
    """AC-58, AC-60: Get match candidates for a report with strictly whitelisted public found summary."""
    report_stmt = select(ItemReport).where(ItemReport.id == report_id)
    report = (await db.execute(report_stmt)).scalar_one_or_none()
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="report_not_found",
        )

    # AC-58: Owner-only (or staff); foreign users get 404 anti-enumeration
    is_staff = current_user.role in ("moderator", "admin")
    if not is_staff and report.reporter_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="report_not_found",
        )

    # Fetch active candidates
    is_lost = report.type == "lost"
    cand_stmt = (
        select(MatchCandidate)
        .options(
            selectinload(MatchCandidate.found_report).selectinload(ItemReport.images),
        )
        .where(
            MatchCandidate.lost_id == report_id
            if is_lost
            else MatchCandidate.found_id == report_id,
            MatchCandidate.status == "suggested",
        )
        .order_by(MatchCandidate.combined_score.desc())
        .limit(limit)
    )
    candidates = list((await db.execute(cand_stmt)).scalars().all())

    responses: list[MatchCandidateResponse] = []
    for cand in candidates:
        found_item = cand.found_report
        # Resolve building name and ID (guaranteeing no floor/room leaks)
        building_id, building_name = await resolve_building_for_location(db, found_item.location_id)

        # First approved public image thumbnail
        public_thumb = None
        for img in found_item.images:
            if img.is_public and img.moderation_status == "approved" and img.deleted_at is None:
                public_thumb = f"/api/images/{img.id}?thumb=1"
                break

        summary = PublicFoundItemSummary(
            id=found_item.id,
            title=found_item.title,
            category=found_item.category,
            description=found_item.description,
            date=found_item.window_start.date().isoformat(),
            building=building_name,
            building_id=building_id,
            thumbnail_url=public_thumb,
            created_at=found_item.created_at,
        )

        responses.append(
            MatchCandidateResponse(
                id=cand.id,
                lost_id=cand.lost_id,
                found_id=cand.found_id,
                found_report=summary,
                score=round(cand.combined_score, 4),
                bin=cand.bin,
                text_score=round(cand.text_score, 4) if cand.text_score is not None else None,
                image_score=round(cand.image_score, 4) if cand.image_score is not None else None,
                location_score=round(cand.location_score, 4)
                if cand.location_score is not None
                else None,
                time_score=round(cand.time_score, 4) if cand.time_score is not None else None,
                explanation=cand.explanation,
                status=cand.status,
                created_at=cand.created_at,
            )
        )

    return MatchListResponse(matches=responses, total=len(responses))


@router.post(
    "/api/matches/{candidate_id}/dismiss",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_csrf)],
)
async def dismiss_match(
    candidate_id: uuid.UUID,
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """AC-61: Dismiss a match candidate permanently for the user."""
    try:
        await dismiss_candidate(
            db=db,
            candidate_id=candidate_id,
            user_id=current_user.id,
            user_role=current_user.role,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="candidate_not_found",
        ) from exc

    return {"status": "dismissed"}
