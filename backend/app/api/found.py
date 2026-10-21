import base64
import uuid
from datetime import UTC, date, datetime, time

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_authenticated_user
from app.core.database import get_db
from app.core.rate_limit import browse_rate_limiter
from app.domain.categories import is_sensitive_category
from app.models.report import ItemImage, ItemReport
from app.models.user import User
from app.schemas.claims import ClaimFormResponse
from app.schemas.found import PublicFoundItemListResponse, PublicFoundItemSummary
from app.services.location import (
    get_descendant_location_ids,
    resolve_building_for_location,
    resolve_buildings_batch,
)

router = APIRouter(prefix="/api/found", tags=["found"])


def _parse_filter_date(val: str, is_end_of_day: bool = False) -> datetime:
    """Parse date (YYYY-MM-DD) or ISO datetime string into UTC datetime."""
    val = val.strip()
    if len(val) == 10 and val.count("-") == 2:
        d = date.fromisoformat(val)
        t = time.max if is_end_of_day else time.min
        return datetime.combine(d, t).replace(tzinfo=UTC)

    dt = datetime.fromisoformat(val)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


@router.get("", response_model=PublicFoundItemListResponse)
async def list_found_items(
    q: str | None = None,
    category: str | None = None,
    building_id: uuid.UUID | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> PublicFoundItemListResponse:
    # 1. AC-43 Browse rate limiting (120 req/min per user)
    is_limited, retry_after = browse_rate_limiter.check_and_record(str(current_user.id))
    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "rate_limited", "message": "Browse rate limit exceeded (120 req/min)"},
            headers={"Retry-After": str(retry_after)},
        )

    # 2. AC-38 Base query: only found items with status == 'open'
    stmt = select(ItemReport).where(
        ItemReport.type == "found",
        ItemReport.status == "open",
    )

    # 3. AC-41 Full-text search on title and description
    if q and q.strip():
        search_query = q.strip()
        ts_vector = func.to_tsvector(
            "english",
            func.concat(ItemReport.title, " ", ItemReport.description),
        )
        ts_query = func.plainto_tsquery("english", search_query)
        stmt = stmt.where(ts_vector.op("@@")(ts_query))

    # 4. AC-41 Category filter
    if category:
        stmt = stmt.where(ItemReport.category == category)

    # 5. AC-41 Building filter (including all descendant floors/rooms)
    if building_id:
        descendant_ids = await get_descendant_location_ids(db, building_id)
        if not descendant_ids:
            return PublicFoundItemListResponse(items=[], next_cursor=None)
        stmt = stmt.where(ItemReport.location_id.in_(descendant_ids))

    # 6. AC-41 Date range filter
    if date_from:
        dt_from = _parse_filter_date(date_from, is_end_of_day=False)
        stmt = stmt.where(ItemReport.window_end >= dt_from)
    if date_to:
        dt_to = _parse_filter_date(date_to, is_end_of_day=True)
        stmt = stmt.where(ItemReport.window_start <= dt_to)

    # 7. AC-41 Stable cursor pagination (ORDER BY created_at DESC, id DESC)
    if cursor:
        try:
            decoded = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
            cur_created_iso, cur_id_str = decoded.split("|")
            cur_created_at = datetime.fromisoformat(cur_created_iso)
            cur_id = uuid.UUID(cur_id_str)
            stmt = stmt.where(
                or_(
                    ItemReport.created_at < cur_created_at,
                    and_(
                        ItemReport.created_at == cur_created_at,
                        ItemReport.id < cur_id,
                    ),
                )
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="invalid_cursor",
            ) from exc

    stmt = stmt.order_by(ItemReport.created_at.desc(), ItemReport.id.desc()).limit(limit + 1)
    result = await db.execute(stmt)
    reports = list(result.scalars().all())

    has_more = len(reports) > limit
    returned_reports = reports[:limit]

    next_cursor = None
    if has_more and returned_reports:
        last_item = returned_reports[-1]
        raw_cursor = f"{last_item.created_at.isoformat()}|{last_item.id}"
        next_cursor = base64.urlsafe_b64encode(raw_cursor.encode("utf-8")).decode("ascii")

    # 8. Resolve building for all returned items
    location_ids = [r.location_id for r in returned_reports]
    building_map = await resolve_buildings_batch(db, location_ids)

    # 9. Load public images for returned items
    report_ids = [r.id for r in returned_reports]
    image_map: dict[uuid.UUID, str] = {}
    if report_ids:
        img_stmt = select(ItemImage).where(
            ItemImage.report_id.in_(report_ids),
            ItemImage.is_public.is_(True),
            ItemImage.deleted_at.is_(None),
        )
        img_res = await db.execute(img_stmt)
        for img in img_res.scalars().all():
            if img.report_id not in image_map:
                image_map[img.report_id] = f"/api/images/{img.storage_key}"

    # 10. AC-39 Build whitelisted public summaries
    items: list[PublicFoundItemSummary] = []
    for r in returned_reports:
        bldg_id, bldg_name = building_map.get(r.location_id, (None, None))
        # AC-30 / AC-39: Sensitive categories never show public photos
        thumb_url = None if is_sensitive_category(r.category) else image_map.get(r.id)

        items.append(
            PublicFoundItemSummary(
                id=r.id,
                title=r.title,
                category=r.category,
                description=r.description,
                date=r.window_start.strftime("%Y-%m-%d"),
                building=bldg_name,
                building_id=bldg_id,
                thumbnail_url=thumb_url,
                created_at=r.created_at,
            )
        )

    return PublicFoundItemListResponse(items=items, next_cursor=next_cursor)


@router.get("/{found_id}/claim-form", response_model=ClaimFormResponse)
async def get_claim_form(
    found_id: uuid.UUID,
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> ClaimFormResponse:
    """D-20: the verification questions a claimant must answer (AC-75).

    Shown only here, to a signed-in user who could claim the item; listings and detail views
    never include them (P1). The item's own reporter and non-open items get 404.
    """
    is_limited, retry_after = browse_rate_limiter.check_and_record(str(current_user.id))
    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "rate_limited", "message": "Browse rate limit exceeded (120 req/min)"},
            headers={"Retry-After": str(retry_after)},
        )
    report = await db.get(ItemReport, found_id)
    if (
        report is None
        or report.type != "found"
        or report.status != "open"
        or report.reporter_id == current_user.id
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report_not_found")
    _, building = await resolve_building_for_location(db, report.location_id)
    return ClaimFormResponse(
        found_id=report.id,
        title=report.title,
        category=report.category,
        building=building,
        verification_prompts=[p for p in (report.verification_prompts or []) if p.strip()],
    )
