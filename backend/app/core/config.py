from functools import lru_cache

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
    CORS_ORIGINS_RAW: str = Field(
        default="http://localhost:8080,http://127.0.0.1:8080,http://localhost:3000",
        validation_alias="CORS_ORIGINS",
    )

    @property
    def CORS_ORIGINS(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS_RAW.split(",") if o.strip()]

    SESSION_MAX_AGE_SECONDS: int = 604800  # 7 days


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
