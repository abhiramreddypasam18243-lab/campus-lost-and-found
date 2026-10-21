from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.jobs import WorkerHeartbeat
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/api/health", response_model=HealthResponse)
async def check_health(db: AsyncSession = Depends(get_db)) -> HealthResponse | JSONResponse:
    """Check system health including database and worker status."""
    db_status = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"

    # D5: worker status from the newest heartbeat ("unknown" if no worker has ever run)
    worker_status = "unknown"
    if db_status == "ok":
        last_seen = (await db.execute(select(func.max(WorkerHeartbeat.last_seen_at)))).scalar()
        if last_seen is not None:
            age = (datetime.now(UTC) - last_seen).total_seconds()
            worker_status = "ok" if age <= settings.WORKER_HEARTBEAT_STALE_SECONDS else "stale"

    is_healthy = db_status == "ok"
    response_content = HealthResponse(
        status="ok" if is_healthy else "degraded",
        database=db_status,
        worker=worker_status,
        version="1.0.0",
        environment=settings.ENVIRONMENT,
    )

    if not is_healthy:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=response_content.model_dump(),
        )

    return response_content
