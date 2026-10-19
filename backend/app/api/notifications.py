import base64
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_authenticated_user, verify_csrf
from app.core.database import get_db
from app.models.notifications import Notification
from app.models.user import User

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def utc_now() -> datetime:
    return datetime.now(UTC)


class NotificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    event_type: str
    event_key: str
    payload: dict[str, Any]
    read_at: datetime | None
    created_at: datetime


class NotificationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[NotificationResponse]
    next_cursor: str | None


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    filter_status: str = Query(default="all", alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationListResponse:
    """AC-74: Owner-only, paginated in-app notification list supporting read and unread filters."""
    stmt = select(Notification).where(Notification.user_id == current_user.id)

    if filter_status == "unread":
        stmt = stmt.where(Notification.read_at.is_(None))
    elif filter_status == "read":
        stmt = stmt.where(Notification.read_at.is_not(None))

    if cursor:
        try:
            decoded = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
            cur_created_iso, cur_id_str = decoded.split("|")
            cur_created_at = datetime.fromisoformat(cur_created_iso)
            cur_id = uuid.UUID(cur_id_str)
            stmt = stmt.where(
                or_(
                    Notification.created_at < cur_created_at,
                    and_(
                        Notification.created_at == cur_created_at,
                        Notification.id < cur_id,
                    ),
                )
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="invalid_cursor",
            ) from exc

    stmt = stmt.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit + 1)
    result = await db.execute(stmt)
    records = list(result.scalars().all())

    has_more = len(records) > limit
    returned_records = records[:limit]

    next_cursor = None
    if has_more and returned_records:
        last_item = returned_records[-1]
        raw_cursor = f"{last_item.created_at.isoformat()}|{last_item.id}"
        next_cursor = base64.urlsafe_b64encode(raw_cursor.encode("utf-8")).decode("ascii")

    items = [
        NotificationResponse(
            id=n.id,
            event_type=n.event_type,
            event_key=n.event_key,
            payload=n.payload,
            read_at=n.read_at,
            created_at=n.created_at,
        )
        for n in returned_records
    ]
    return NotificationListResponse(items=items, next_cursor=next_cursor)


@router.post(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    dependencies=[Depends(verify_csrf)],
)
async def mark_notification_read(
    notification_id: uuid.UUID,
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationResponse:
    """AC-74: Mark notification as read. Returns 404 for notifications belonging to other users."""
    stmt = select(Notification).where(Notification.id == notification_id)
    notif = (await db.execute(stmt)).scalar_one_or_none()

    if notif is None or notif.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="notification_not_found",
        )

    if notif.read_at is None:
        notif.read_at = utc_now()
        await db.commit()
        await db.refresh(notif)

    return NotificationResponse(
        id=notif.id,
        event_type=notif.event_type,
        event_key=notif.event_key,
        payload=notif.payload,
        read_at=notif.read_at,
        created_at=notif.created_at,
    )
