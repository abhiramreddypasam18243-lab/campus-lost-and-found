"""Dashboard API endpoints for operational analytics (spec section 15, AC-105 to AC-108)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_session_and_user
from app.core.database import get_db
from app.models.user import Session, User
from app.schemas.analytics import DashboardMetricsResponse
from app.services import analytics as analytics_service

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


async def require_dashboard_staff(
    session_data: tuple[Session, User] | None = Depends(get_current_session_and_user),
) -> User:
    """AC-106: Dashboard is available only to moderators and admins.

    Non-staff and unauthenticated callers receive 404 anti-enumeration.
    """
    if not session_data or session_data[1].role not in ("moderator", "admin"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Not found."},
        )
    return session_data[1]


@router.get("", response_model=DashboardMetricsResponse)
async def get_dashboard(
    current_user: User = Depends(require_dashboard_staff),
    db: AsyncSession = Depends(get_db),
) -> DashboardMetricsResponse:
    """AC-105, AC-106, AC-107, AC-108: Retrieve operational metrics and recovery statistics."""
    return await analytics_service.get_dashboard_analytics(db)
