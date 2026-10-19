from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import auth, health
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
                    content={"code": "request_entity_too_large", "message": "Request body exceeds 1 MB limit."},
                )
        response: Response = await call_next(request)
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle management."""
    yield


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
