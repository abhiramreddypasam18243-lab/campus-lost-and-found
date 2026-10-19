import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_authenticated_user, verify_csrf
from app.core.database import get_db
from app.models.embeddings import ModelRegistry
from app.models.jobs import BackgroundJob
from app.models.user import User
from app.services.embeddings import activate_model_version

router = APIRouter(prefix="/api/admin", tags=["admin"])


def utc_now() -> datetime:
    return datetime.now(UTC)


def require_admin_user(current_user: User = Depends(require_authenticated_user)) -> User:
    """Ensure caller has admin role; returns 404 anti-enumeration for non-admins."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="not_found",
        )
    return current_user


class AdminJobResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    kind: str
    entity_id: uuid.UUID
    payload: dict[str, Any]
    status: str
    attempts: int
    max_attempts: int
    run_after: datetime
    last_error: str | None
    created_at: datetime


class AdminJobListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jobs: list[AdminJobResponse]


class ActivateModelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_type: str
    model_name: str
    model_version: str
    dimension: int = 384


class ModelRegistryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    model_type: str
    model_name: str
    model_version: str
    dimension: int
    is_active: bool
    created_at: datetime


@router.get("/jobs", response_model=AdminJobListResponse)
async def list_admin_jobs(
    status: str | None = None,
    current_admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
) -> AdminJobListResponse:
    """AC-47: View failed and running background jobs."""
    stmt = select(BackgroundJob)
    if status:
        stmt = stmt.where(BackgroundJob.status == status)
    stmt = stmt.order_by(BackgroundJob.created_at.desc()).limit(100)

    result = await db.execute(stmt)
    jobs = list(result.scalars().all())

    return AdminJobListResponse(
        jobs=[
            AdminJobResponse(
                id=j.id,
                kind=j.kind,
                entity_id=j.entity_id,
                payload=j.payload,
                status=j.status,
                attempts=j.attempts,
                max_attempts=j.max_attempts,
                run_after=j.run_after,
                last_error=j.last_error,
                created_at=j.created_at,
            )
            for j in jobs
        ]
    )


@router.post(
    "/jobs/{job_id}/retry",
    response_model=AdminJobResponse,
    dependencies=[Depends(verify_csrf)],
)
async def retry_job(
    job_id: uuid.UUID,
    current_admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
) -> AdminJobResponse:
    """AC-47: Manual retry of a failed job."""
    stmt = select(BackgroundJob).where(BackgroundJob.id == job_id)
    job = (await db.execute(stmt)).scalar_one_or_none()

    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found")

    job.status = "pending"
    job.attempts = 0
    job.last_error = None
    job.run_after = utc_now()
    job.locked_at = None
    job.locked_by = None
    await db.commit()
    await db.refresh(job)

    return AdminJobResponse(
        id=job.id,
        kind=job.kind,
        entity_id=job.entity_id,
        payload=job.payload,
        status=job.status,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        run_after=job.run_after,
        last_error=job.last_error,
        created_at=job.created_at,
    )


@router.get("/models", response_model=list[ModelRegistryResponse])
async def list_models(
    current_admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[ModelRegistryResponse]:
    """AC-49: List models in registry."""
    stmt = select(ModelRegistry).order_by(ModelRegistry.created_at.desc())
    models = list((await db.execute(stmt)).scalars().all())
    return [
        ModelRegistryResponse(
            id=m.id,
            model_type=m.model_type,
            model_name=m.model_name,
            model_version=m.model_version,
            dimension=m.dimension,
            is_active=m.is_active,
            created_at=m.created_at,
        )
        for m in models
    ]


@router.post(
    "/models/activate",
    response_model=ModelRegistryResponse,
    dependencies=[Depends(verify_csrf)],
)
async def activate_model(
    payload: ActivateModelRequest,
    current_admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
) -> ModelRegistryResponse:
    """AC-49: Activate model version and enqueue backfills."""
    reg = await activate_model_version(
        db=db,
        model_type=payload.model_type,
        model_name=payload.model_name,
        model_version=payload.model_version,
        dimension=payload.dimension,
    )
    await db.commit()
    await db.refresh(reg)

    return ModelRegistryResponse(
        id=reg.id,
        model_type=reg.model_type,
        model_name=reg.model_name,
        model_version=reg.model_version,
        dimension=reg.dimension,
        is_active=reg.is_active,
        created_at=reg.created_at,
    )
