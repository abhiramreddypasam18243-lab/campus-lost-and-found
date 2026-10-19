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


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    email: str
    display_name: str | None
    role: str
    status: str
    created_at: datetime


class UpdateUserRoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str


class RetentionRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expired_reports: int
    purged_images: int
    purged_audit_logs: int


@router.get("/users", response_model=list[AdminUserResponse])
async def list_admin_users(
    current_admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[AdminUserResponse]:
    """AC-99: Admin view of users."""
    stmt = select(User).order_by(User.created_at.desc())
    users = list((await db.execute(stmt)).scalars().all())
    return [
        AdminUserResponse(
            id=u.id,
            email=u.email,
            display_name=u.display_name,
            role=u.role,
            status=u.status,
            created_at=u.created_at,
        )
        for u in users
    ]


@router.patch(
    "/users/{user_id}/role",
    response_model=AdminUserResponse,
    dependencies=[Depends(verify_csrf)],
)
async def update_user_role(
    user_id: uuid.UUID,
    payload: UpdateUserRoleRequest,
    current_admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
) -> AdminUserResponse:
    """AC-99: Change user role with last-admin guard and audit logging."""
    from app.services.user_account import change_user_role

    target = await change_user_role(db, user_id, payload.role, current_admin)
    return AdminUserResponse(
        id=target.id,
        email=target.email,
        display_name=target.display_name,
        role=target.role,
        status=target.status,
        created_at=target.created_at,
    )


@router.post(
    "/retention/run",
    response_model=RetentionRunResponse,
    dependencies=[Depends(verify_csrf)],
)
async def trigger_retention_sweep(
    retention_days: int = 90,
    image_purge_days: int = 30,
    audit_retention_days: int = 365,
    current_admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
) -> RetentionRunResponse:
    """AC-100, AC-101, AC-102: Execute retention sweep job."""
    from app.services.retention import (
        expire_unclaimed_reports,
        purge_closed_images,
        purge_old_audit_logs,
    )

    expired_reports = await expire_unclaimed_reports(db, retention_days=retention_days)
    purged_images = await purge_closed_images(db, purge_days=image_purge_days)
    purged_audit_logs = await purge_old_audit_logs(db, retention_days=audit_retention_days)
    return RetentionRunResponse(
        expired_reports=expired_reports,
        purged_images=purged_images,
        purged_audit_logs=purged_audit_logs,
    )
