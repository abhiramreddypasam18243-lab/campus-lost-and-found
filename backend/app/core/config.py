from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings and environment configuration."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Core Environment
    ENVIRONMENT: str = "development"
    SECRET_KEY: str = "change_this_to_a_secure_random_key_in_production_32chars"
    API_PORT: int = 8000
    FRONTEND_PORT: int = 8080

    # Campus Domain Whitelist
    ALLOWED_EMAIL_DOMAINS: list[str] = ["campus.edu", "student.campus.edu"]

    @field_validator("ALLOWED_EMAIL_DOMAINS", mode="before")
    @classmethod
    def parse_allowed_domains(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return [d.strip().lower() for d in v.split(",") if d.strip()]
        if isinstance(v, list):
            return [str(d).strip().lower() for d in v if str(d).strip()]
        return ["campus.edu", "student.campus.edu"]

    # Database
    POSTGRES_USER: str = "campus_user"
    POSTGRES_PASSWORD: str = "campus_secure_password"
    POSTGRES_DB: str = "campus_lost_and_found"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = "postgresql+asyncpg://campus_user:campus_secure_password@localhost:5432/campus_lost_and_found"
    SYNC_DATABASE_URL: str = "postgresql+psycopg://campus_user:campus_secure_password@localhost:5432/campus_lost_and_found"

    # Mail / SMTP
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_FROM: str = "no-reply@campus.edu"

    # Retention Periods (in days)
    RETENTION_UNCLAIMED_FOUND_DAYS: int = 90
    RETENTION_CLOSED_IMAGE_DAYS: int = 30
    RETENTION_CLOSED_CLAIM_EVIDENCE_DAYS: int = 30
    RETENTION_AUDIT_LOG_DAYS: int = 365

    # ML Models
    TEXT_MODEL_NAME: str = "all-MiniLM-L6-v2"
    TEXT_MODEL_VERSION: str = "v1"
    CLIP_MODEL_NAME: str = "ViT-B/32"
    CLIP_MODEL_VERSION: str = "v1"

    # Security & CORS
    CORS_ORIGINS: list[str] = ["http://localhost:8080", "http://127.0.0.1:8080", "http://localhost:3000"]
    SESSION_MAX_AGE_SECONDS: int = 604800  # 7 days

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        if isinstance(v, list):
            return [str(o).strip() for o in v if str(o).strip()]
        return ["http://localhost:8080", "http://127.0.0.1:8080"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
