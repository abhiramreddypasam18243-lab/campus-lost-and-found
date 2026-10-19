from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import browse_rate_limiter
from app.core.security import login_rate_limiter
from app.main import app

settings = get_settings()

test_engine = create_async_engine(
    settings.DATABASE_URL,
    poolclass=NullPool,
    echo=False,
)

TestAsyncSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(autouse=True)
async def clean_database_and_state() -> AsyncGenerator[None, None]:
    """Clean test tables and in-memory rate limit state before and after each test."""
    login_rate_limiter.attempts.clear()
    browse_rate_limiter.reset()
    async with TestAsyncSessionLocal() as session:
        try:
            await session.execute(
                text(
                    "TRUNCATE TABLE users, email_tokens, sessions, audit_log, location_adjacency, campus_locations, item_images, item_reports, jobs, model_registry, text_embeddings, image_embeddings, notifications, match_feedback, match_candidates, claims, handovers RESTART IDENTITY CASCADE;"
                )
            )
            await session.commit()

        except Exception:
            await session.rollback()

    yield
    login_rate_limiter.attempts.clear()
    browse_rate_limiter.reset()


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an isolated database session with NullPool for event loop safety."""
    async with TestAsyncSessionLocal() as session:
        yield session


@pytest.fixture
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an asynchronous HTTP client wired to the isolated database session."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    app.dependency_overrides.clear()
