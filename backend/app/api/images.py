from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_authenticated_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models.report import ItemImage, ItemReport
from app.models.user import User

settings = get_settings()
router = APIRouter(prefix="/api/images", tags=["images"])


@router.get("/{storage_key}")
async def get_image(
    storage_key: str,
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """AC-35: Authorized image serving route checking visibility."""
    # Lookup image record
    stmt = (
        select(ItemImage, ItemReport)
        .join(ItemReport, ItemImage.report_id == ItemReport.id)
        .where(
            ItemImage.storage_key == storage_key,
            ItemImage.deleted_at.is_(None),
        )
    )
    result = await db.execute(stmt)
    row = result.first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="image_not_found")

    image, report = row

    # Check visibility: private images return 404 to non-owner non-staff (anti-enumeration)
    is_staff = current_user.role in ("moderator", "admin")
    is_owner = current_user.id == report.reporter_id

    if not image.is_public and not (is_owner or is_staff):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="image_not_found")

    file_path = Path(settings.UPLOAD_DIR) / image.storage_key
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="file_not_found")

    return FileResponse(
        path=file_path,
        media_type=image.original_mime,
        headers={"X-Content-Type-Options": "nosniff"},
    )
