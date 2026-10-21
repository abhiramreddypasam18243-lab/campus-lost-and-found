import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import require_authenticated_user, verify_csrf
from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import browse_rate_limiter
from app.domain.categories import is_sensitive_category
from app.domain.image_hash import hamming_distance
from app.domain.lifecycle import transition_found_report, transition_lost_report
from app.domain.pii import scan_pii
from app.domain.time import compute_time_window
from app.models.location import CampusLocation
from app.models.report import ItemImage, ItemReport
from app.models.user import User
from app.schemas.found import (
    FullStaffReportResponse,
    LocationDetail,
    PublicImageDetail,
    PublicReportDetailResponse,
    ReporterSummary,
)
from app.schemas.report import (
    CreateFoundReportRequest,
    CreateLostReportRequest,
    ImageResponse,
    ReportResponse,
)
from app.services.audit import write_audit_log
from app.services.job_queue import enqueue_job
from app.services.location import resolve_building_for_location
from app.services.photo import process_and_save_photo

settings = get_settings()
router = APIRouter(prefix="/api/reports", tags=["reports"])


def utc_now() -> datetime:
    return datetime.now(UTC)


def _to_report_response(report: ItemReport, viewer: User) -> ReportResponse:
    """Build response applying visibility rules (P1 default-deny)."""
    is_staff = viewer.role in ("moderator", "admin")
    is_owner = viewer.id == report.reporter_id

    # Mask private details and verification prompts for normal users who don't own the report
    show_private = is_owner or is_staff
    private_details = report.private_details if show_private else None
    verification_prompts = report.verification_prompts if show_private else []

    report_images = getattr(report, "images", None) or []
    images = [
        ImageResponse(
            id=img.id,
            storage_key=img.storage_key,
            width=img.width,
            height=img.height,
            is_public=img.is_public,
            dhash=img.dhash,
            created_at=img.created_at,
        )
        for img in report_images
        if img.deleted_at is None and (img.is_public or show_private)
    ]

    return ReportResponse(
        id=report.id,
        type=report.type,
        status=report.status,
        title=report.title,
        description=report.description,
        category=report.category,
        location_id=report.location_id,
        reporter_id=report.reporter_id,
        window_start=report.window_start,
        window_end=report.window_end,
        time_precision=report.time_precision,
        private_details=private_details,
        verification_prompts=verification_prompts,
        images=images,
        created_at=report.created_at,
    )


@router.post(
    "/lost",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_csrf)],
)
async def create_lost_report(
    payload: CreateLostReportRequest,
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> ReportResponse:
    # 1. PII Scan (AC-28, AC-29)
    for field_name, field_val in (("title", payload.title), ("description", payload.description)):
        detected_kind = scan_pii(field_val)
        if detected_kind is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"code": "pii_detected", "kind": detected_kind, "field": field_name},
            )

    # 2. Location verification
    loc_res = await db.execute(
        select(CampusLocation).where(CampusLocation.id == payload.location_id)
    )
    if loc_res.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="location_not_found")

    # 3. Time Window calculation (AC-23)
    start_utc, end_utc = compute_time_window(
        ref_date=payload.date,
        precision=payload.time_precision,
        tz_name=current_user.timezone or "Asia/Kolkata",
        exact_time=payload.exact_time,
    )

    report_id = uuid.uuid4()
    report = ItemReport(
        id=report_id,
        type="lost",
        status="open",
        title=payload.title.strip(),
        description=payload.description.strip(),
        category=payload.category,
        location_id=payload.location_id,
        reporter_id=current_user.id,
        window_start=start_utc,
        window_end=end_utc,
        time_precision=payload.time_precision,
    )
    db.add(report)
    await enqueue_job(db, kind="embed_report_text", entity_id=report_id)
    await write_audit_log(
        db=db,
        actor_id=current_user.id,
        role=current_user.role,
        action="create_lost_report",
        entity_type="item_report",
        entity_id=report_id,
        summary={"category": report.category, "location_id": str(report.location_id)},
    )
    await db.commit()
    await db.refresh(report)

    return _to_report_response(report, current_user)


@router.post(
    "/found",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_csrf)],
)
async def create_found_report(
    payload: CreateFoundReportRequest,
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> ReportResponse:
    # 1. PII Scan on public fields (AC-28, AC-29)
    for field_name, field_val in (("title", payload.title), ("description", payload.description)):
        detected_kind = scan_pii(field_val)
        if detected_kind is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"code": "pii_detected", "kind": detected_kind, "field": field_name},
            )

    # 2. Location verification
    loc_res = await db.execute(
        select(CampusLocation).where(CampusLocation.id == payload.location_id)
    )
    if loc_res.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="location_not_found")

    # 3. Time Window calculation (AC-23)
    start_utc, end_utc = compute_time_window(
        ref_date=payload.date,
        precision=payload.time_precision,
        tz_name=current_user.timezone or "Asia/Kolkata",
        exact_time=payload.exact_time,
    )

    report_id = uuid.uuid4()
    report = ItemReport(
        id=report_id,
        type="found",
        status="pending_review",  # AC-22: Starts as pending_review
        title=payload.title.strip(),
        description=payload.description.strip(),
        category=payload.category,
        location_id=payload.location_id,
        reporter_id=current_user.id,
        window_start=start_utc,
        window_end=end_utc,
        time_precision=payload.time_precision,
        private_details=payload.private_details.strip() if payload.private_details else None,
        verification_prompts=[p.strip() for p in payload.verification_prompts],
    )
    db.add(report)
    await enqueue_job(db, kind="embed_report_text", entity_id=report_id)
    await write_audit_log(
        db=db,
        actor_id=current_user.id,
        role=current_user.role,
        action="create_found_report",
        entity_type="item_report",
        entity_id=report_id,
        summary={"category": report.category, "location_id": str(report.location_id)},
    )
    await db.commit()
    await db.refresh(report)

    return _to_report_response(report, current_user)


@router.get("/mine", response_model=list[ReportResponse])
async def list_my_reports(
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> list[ReportResponse]:
    """Spec 9: the caller's own lost and found reports, newest first (owner view)."""
    stmt = (
        select(ItemReport)
        .options(selectinload(ItemReport.images))
        .where(ItemReport.reporter_id == current_user.id)
        .order_by(ItemReport.created_at.desc())
    )
    reports = (await db.execute(stmt)).scalars().all()
    return [_to_report_response(r, current_user) for r in reports]


@router.get(
    "/{report_id}",
    response_model=PublicReportDetailResponse | FullStaffReportResponse,
)
async def get_report(
    report_id: uuid.UUID,
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> PublicReportDetailResponse | FullStaffReportResponse:
    # 1. AC-43 Browse rate limiting (120 req/min per user)
    is_limited, retry_after = browse_rate_limiter.check_and_record(str(current_user.id))
    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "rate_limited", "message": "Browse rate limit exceeded (120 req/min)"},
            headers={"Retry-After": str(retry_after)},
        )

    stmt = select(ItemReport).where(ItemReport.id == report_id)
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()

    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report_not_found")

    is_staff = current_user.role in ("moderator", "admin")
    is_owner = current_user.id == report.reporter_id

    # AC-40: Lost reports visible only to reporter, moderators, and admins
    if report.type == "lost" and not (is_owner or is_staff):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report_not_found")

    # Found reports not yet open (e.g. pending_review, removed) visible only to reporter or staff
    if report.type == "found" and report.status != "open" and not (is_owner or is_staff):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report_not_found")

    # Load associated images
    img_stmt = (
        select(ItemImage)
        .where(ItemImage.report_id == report.id, ItemImage.deleted_at.is_(None))
        .order_by(ItemImage.created_at.asc())
    )
    images = list((await db.execute(img_stmt)).scalars().all())

    # AC-42: Staff and owners see full details
    if is_owner or is_staff:
        loc_stmt = select(CampusLocation).where(CampusLocation.id == report.location_id)
        loc = (await db.execute(loc_stmt)).scalar_one_or_none()
        location_detail = (
            LocationDetail(
                id=loc.id,
                name=loc.name,
                kind=loc.kind,
                parent_id=loc.parent_id,
                lat=float(loc.lat) if loc.lat is not None else None,
                lng=float(loc.lng) if loc.lng is not None else None,
            )
            if loc
            else None
        )

        rep_stmt = select(User).where(User.id == report.reporter_id)
        rep = (await db.execute(rep_stmt)).scalar_one_or_none()
        reporter_summary = (
            ReporterSummary(
                id=rep.id,
                email=rep.email,
                display_name=rep.display_name,
            )
            if rep
            else None
        )

        staff_images = [
            ImageResponse(
                id=img.id,
                storage_key=img.storage_key,
                width=img.width,
                height=img.height,
                is_public=img.is_public,
                dhash=img.dhash,
                created_at=img.created_at,
            )
            for img in images
        ]

        return FullStaffReportResponse(
            id=report.id,
            type=report.type,
            status=report.status,
            title=report.title,
            description=report.description,
            category=report.category,
            location_id=report.location_id,
            location=location_detail,
            reporter_id=report.reporter_id,
            reporter=reporter_summary,
            window_start=report.window_start,
            window_end=report.window_end,
            time_precision=report.time_precision,
            private_details=report.private_details,
            verification_prompts=report.verification_prompts,
            images=staff_images,
            disposition=report.disposition,
            closed_at=report.closed_at,
            reviewed_by=report.reviewed_by,
            created_at=report.created_at,
            updated_at=report.updated_at,
        )

    # AC-39: Normal students see only whitelisted public detail
    bldg_id, bldg_name = await resolve_building_for_location(db, report.location_id)

    public_images: list[PublicImageDetail] = []
    if not is_sensitive_category(report.category):
        for img in images:
            if img.is_public:
                public_images.append(
                    PublicImageDetail(
                        id=img.id,
                        thumbnail_url=f"/api/images/{img.storage_key}",
                        image_url=f"/api/images/{img.storage_key}",
                    )
                )

    return PublicReportDetailResponse(
        id=report.id,
        type=report.type,
        status=report.status,
        title=report.title,
        description=report.description,
        category=report.category,
        date=report.window_start.strftime("%Y-%m-%d"),
        building=bldg_name,
        building_id=bldg_id,
        images=public_images,
        created_at=report.created_at,
    )


@router.patch(
    "/{report_id}/close",
    response_model=ReportResponse,
    dependencies=[Depends(verify_csrf)],
)
async def close_report(
    report_id: uuid.UUID,
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> ReportResponse:
    """AC-27: A reporter can close their own report; closing someone else's returns 404."""
    stmt = select(ItemReport).where(ItemReport.id == report_id)
    report = (await db.execute(stmt)).scalar_one_or_none()

    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report_not_found")

    is_staff = current_user.role in ("moderator", "admin")
    is_owner = current_user.id == report.reporter_id

    # Foreign closure returns 404 per AC-27
    if not (is_owner or is_staff):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report_not_found")

    # Lifecycle transition validation (AC-25, AC-26, AC-27)
    try:
        if report.type == "found":
            new_status = transition_found_report(report.status, "close")
        else:
            new_status = transition_lost_report(report.status, "close")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "invalid_transition", "message": str(exc)},
        ) from exc

    report.status = new_status
    report.closed_at = utc_now()
    await db.commit()
    await db.refresh(report)

    await write_audit_log(
        db=db,
        actor_id=current_user.id,
        role=current_user.role,
        action="close_report",
        entity_type="item_report",
        entity_id=report.id,
    )
    await db.commit()

    return _to_report_response(report, current_user)


@router.post(
    "/{report_id}/images",
    response_model=ImageResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_csrf)],
)
async def upload_report_image(
    report_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> ImageResponse:
    stmt = select(ItemReport).where(ItemReport.id == report_id)
    report = (await db.execute(stmt)).scalar_one_or_none()

    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report_not_found")

    is_staff = current_user.role in ("moderator", "admin")
    is_owner = current_user.id == report.reporter_id
    if not (is_owner or is_staff):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report_not_found")

    # AC-36: 4th image on one report returns 422
    count_stmt = select(func.count(ItemImage.id)).where(
        ItemImage.report_id == report_id,
        ItemImage.deleted_at.is_(None),
    )
    current_count = (await db.execute(count_stmt)).scalar() or 0
    if current_count >= 3:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "max_images_exceeded",
                "message": "At most 3 images are allowed per report.",
            },
        )

    content = await file.read()
    processed = process_and_save_photo(content, settings.UPLOAD_DIR)

    # AC-30: Sensitive categories (id_card, wallet) are non-public automatically
    is_public = False if is_sensitive_category(report.category) else True

    # AC-37: Check difference hash against other users' found reports for duplicate image detection
    if report.type == "found":
        other_images_stmt = (
            select(ItemImage)
            .join(ItemReport, ItemImage.report_id == ItemReport.id)
            .where(
                ItemReport.type == "found",
                ItemReport.reporter_id != current_user.id,
                ItemImage.deleted_at.is_(None),
            )
        )
        other_images = (await db.execute(other_images_stmt)).scalars().all()
        for other in other_images:
            dist = hamming_distance(processed.dhash, other.dhash)
            if dist <= 4:
                # Flag duplicate image for moderators in audit log
                await write_audit_log(
                    db=db,
                    actor_id=current_user.id,
                    role=current_user.role,
                    action="duplicate_image_flagged",
                    entity_type="item_image",
                    entity_id=other.id,
                    summary={"distance": dist, "target_report_id": str(report.id)},
                )
                break

    image_id = uuid.uuid4()
    img_record = ItemImage(
        id=image_id,
        report_id=report.id,
        storage_key=processed.storage_key,
        original_mime=processed.original_mime,
        sha256=processed.sha256,
        dhash=processed.dhash,
        width=processed.width,
        height=processed.height,
        is_public=is_public,
        moderation_status="approved" if is_staff else "pending",
    )
    db.add(img_record)
    await enqueue_job(
        db,
        kind="embed_report_image",
        entity_id=image_id,
        payload={"report_id": str(report.id)},
    )
    await db.commit()
    await db.refresh(img_record)

    return ImageResponse(
        id=img_record.id,
        storage_key=img_record.storage_key,
        width=img_record.width,
        height=img_record.height,
        is_public=img_record.is_public,
        dhash=img_record.dhash,
        created_at=img_record.created_at,
    )
