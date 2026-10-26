import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import (
    admin,
    auth,
    claims,
    dashboard,
    found,
    handover,
    health,
    images,
    locations,
    matches,
    moderation,
    notifications,
    reports,
)
from app.core.config import get_settings

settings = get_settings()

MAX_NON_UPLOAD_BODY_BYTES = 1024 * 1024  # 1 MB (AC-15, SEC8)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforce required security headers on all responses."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'; script-src 'self';"
        )
        return response


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """AC-15 & SEC8: Reject non-upload request bodies exceeding 1 MB with HTTP 413."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        content_length = request.headers.get("content-length")
        # Exclude multi-part image uploads handled separately
        is_upload = "/images" in request.url.path
        if content_length and not is_upload:
            if int(content_length) > MAX_NON_UPLOAD_BODY_BYTES:
                return JSONResponse(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    content={
                        "code": "request_entity_too_large",
                        "message": "Request body exceeds 1 MB limit.",
                    },
                )
        response: Response = await call_next(request)
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle management."""
    worker_task = None
    if settings.RUN_WORKER_IN_PROCESS:
        try:
            from app.worker.main import run_worker_loop

            worker_task = asyncio.create_task(run_worker_loop())
        except Exception:
            pass
    try:
        yield
    finally:
        if worker_task:
            worker_task.cancel()
            try:
                await worker_task
            except (asyncio.CancelledError, Exception):
                pass


app = FastAPI(
    title="Smart Campus Lost and Found API",
    version="1.0.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Security & Body Size Middlewares
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(MaxBodySizeMiddleware)

# Include Routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(locations.router)
app.include_router(reports.router)
app.include_router(found.router)
app.include_router(images.router)
app.include_router(notifications.router)
app.include_router(matches.router)
app.include_router(claims.router)
app.include_router(handover.router)
app.include_router(moderation.router)
app.include_router(admin.router)
app.include_router(dashboard.router)

# Mount Frontend SPA if frontend/dist exists
frontend_dist_candidates = [
    Path(__file__).resolve().parent.parent.parent / "frontend" / "dist",
    Path("/app/frontend/dist"),
    Path(__file__).resolve().parent.parent / "frontend" / "dist",
]
frontend_dist = next(
    (p for p in frontend_dist_candidates if p.exists() and (p / "index.html").exists()), None
)

if frontend_dist is not None:
    dist_dir: Path = frontend_dist
    assets_dir = dist_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend_assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(request: Request, full_path: str) -> Response:
        if (
            full_path.startswith("api/")
            or full_path == "api"
            or full_path.startswith("docs")
            or full_path.startswith("openapi.json")
        ):
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"code": "not_found", "message": "Not found"},
            )
        target_file = dist_dir / full_path
        if target_file.is_file():
            return FileResponse(target_file)
        return FileResponse(dist_dir / "index.html")
