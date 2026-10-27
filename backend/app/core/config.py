from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings and environment configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core Environment
    ENVIRONMENT: str = "development"
    SECRET_KEY: str = "change_this_to_a_secure_random_key_in_production_32chars"
    API_PORT: int = 8000
    FRONTEND_PORT: int = 8080
    UPLOAD_DIR: str = "uploads"

    # Campus Domain Whitelist (parsed from comma-separated string)
    ALLOWED_EMAIL_DOMAINS_RAW: str = Field(
        default="campus.edu,student.campus.edu,iisc.ac.in",
        validation_alias="ALLOWED_EMAIL_DOMAINS",
    )

    @property
    def ALLOWED_EMAIL_DOMAINS(self) -> list[str]:
        return [d.strip().lower() for d in self.ALLOWED_EMAIL_DOMAINS_RAW.split(",") if d.strip()]

    # Database
    POSTGRES_USER: str = "campus_user"
    POSTGRES_PASSWORD: str = "campus_secure_password"
    POSTGRES_DB: str = "campus_lost_and_found"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = "postgresql+asyncpg://campus_user:campus_secure_password@localhost:5432/campus_lost_and_found"
    SYNC_DATABASE_URL: str = "postgresql+psycopg://campus_user:campus_secure_password@localhost:5432/campus_lost_and_found"
    RUN_WORKER_IN_PROCESS: bool = False

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if "sslmode=require" in url:
            url = url.replace("sslmode=require", "ssl=require")
        elif "sslmode=" in url:
            import re
            url = re.sub(r"sslmode=[a-zA-Z0-9_-]+", "ssl=require", url)
        return url

    @property
    def RESOLVED_SYNC_DATABASE_URL(self) -> str:
        url = self.SYNC_DATABASE_URL
        if not url or url == "postgresql+psycopg://campus_user:campus_secure_password@localhost:5432/campus_lost_and_found":
            url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql+asyncpg://"):
            url = url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
        if "ssl=require" in url:
            url = url.replace("ssl=require", "sslmode=require")
        elif "ssl=true" in url:
            url = url.replace("ssl=true", "sslmode=require")
        return url

    # Mail / SMTP & HTTP Email APIs (D8: Resend/Brevo bypass Render free tier port 587 block)
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_FROM: str = "no-reply@campus.edu"
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_USE_TLS: bool = False
    RESEND_API_KEY: str | None = None
    BREVO_API_KEY: str | None = None
    # Base URL of the web app, used in emailed links (verification)
    APP_BASE_URL: str = "http://localhost:8080"

    # Retention Periods (in days)
    RETENTION_UNCLAIMED_FOUND_DAYS: int = 90
    RETENTION_CLOSED_IMAGE_DAYS: int = 30
    RETENTION_CLOSED_CLAIM_EVIDENCE_DAYS: int = 30
    RETENTION_AUDIT_LOG_DAYS: int = 365

    # ML Models (D4: weights baked into the image under MODEL_DIR; versions are pinned HF revisions)
    # "standin" = deterministic hash vectors for the fast test suite; "model" = the real models (worker)
    EMBEDDING_BACKEND: Literal["standin", "model"] = "standin"
    MODEL_DIR: str = "/models"
    TEXT_MODEL_NAME: str = "all-MiniLM-L6-v2"
    TEXT_MODEL_VERSION: str = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
    CLIP_MODEL_NAME: str = "clip-ViT-B-32"
    CLIP_MODEL_VERSION: str = "327ab6726d33c0e22f920c83f2ff9e4bd38ca37f"

    # Worker
    WORKER_POLL_SECONDS: float = 2.0
    WORKER_HEARTBEAT_STALE_SECONDS: int = 60
    WORKER_MAINTENANCE_INTERVAL_SECONDS: int = 3600

    # Security & CORS
    CORS_ORIGINS_RAW: str = Field(
        default="http://localhost:8080,http://127.0.0.1:8080,http://localhost:3000",
        validation_alias="CORS_ORIGINS",
    )

    @property
    def CORS_ORIGINS(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS_RAW.split(",") if o.strip()]

    SESSION_MAX_AGE_SECONDS: int = 604800  # 7 days

    # SEC7: only these hosts may vouch for the client's protocol (X-Forwarded-Proto) and network
    # (X-Client-Network). Hostnames are resolved per request. The compose frontend is "frontend".
    TRUSTED_PROXIES_RAW: str = Field(default="frontend", validation_alias="TRUSTED_PROXIES")

    @property
    def TRUSTED_PROXIES(self) -> list[str]:
        return [p.strip() for p in self.TRUSTED_PROXIES_RAW.split(",") if p.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
