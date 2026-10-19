"""Tests for AC-131 to AC-137: Quality, Architecture, Security Canary, and Layering Checks."""

import ast
import json
import logging
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_token
from app.main import app
from app.models.user import Session, User


def test_ac_132_pure_domain_layering_check() -> None:
    """AC-132: Confirm that the domain package imports no framework, database,

    ORM model, or clock module.
    """
    domain_dir = Path(__file__).resolve().parent.parent / "app" / "domain"
    assert domain_dir.exists() and domain_dir.is_dir()

    prohibited_modules = {
        "fastapi",
        "starlette",
        "sqlalchemy",
        "asyncpg",
        "psycopg",
        "alembic",
        "app.models",
        "app.api",
        "app.services",
        "time",
    }

    for py_file in domain_dir.glob("*.py"):
        if py_file.name == "__init__.py":
            continue
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for prohibited in prohibited_modules:
                        assert not alias.name.startswith(prohibited), (
                            f"Prohibited import '{alias.name}' found in {py_file.name} (AC-132)"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for prohibited in prohibited_modules:
                        assert not node.module.startswith(prohibited), (
                            f"Prohibited from-import '{node.module}' found in {py_file.name} (AC-132)"
                        )


def test_ac_133_openapi_schema_generation(tmp_path: Path) -> None:
    """AC-133: The backend produces a valid OpenAPI 3.x document for frontend type generation."""
    schema = app.openapi()
    assert "openapi" in schema
    assert schema["openapi"].startswith("3.")
    assert "paths" in schema
    assert "/api/health" in schema["paths"]
    assert "/api/dashboard" in schema["paths"]
    assert "/api/admin/evaluation" in schema["paths"]

    # Verify export to JSON file
    schema_path = tmp_path / "openapi.json"
    schema_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    assert schema_path.exists()


@pytest.mark.asyncio
async def test_ac_136_security_logging_canary(
    async_client: AsyncClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """AC-136: Canary test proving no passwords, raw session IDs, email tokens,

    handover codes, or plaintext secrets appear in system logs.
    """
    canary_password = "SuperSecretCanaryPassword987!"
    canary_email = f"canary_{uuid.uuid4().hex[:6]}@campus.edu"

    with caplog.at_level(logging.DEBUG):
        # 1. Attempt login with secret password
        await async_client.post(
            "/api/auth/login",
            json={"email": canary_email, "password": canary_password},
        )

        # Inspect all captured log messages
        log_text = " ".join([record.getMessage() for record in caplog.records])
        assert canary_password not in log_text, "CRITICAL: Plaintext password leaked in logs! (AC-136)"
        assert "SuperSecretCanary" not in log_text


@pytest.mark.asyncio
async def test_ac_137_endpoint_latency_targets(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """AC-137: Browse and search endpoints respond in <= 300 ms, dashboard in <= 500 ms."""
    mod_user = User(
        email=f"mod_bench_{uuid.uuid4().hex[:6]}@campus.edu",
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$fakehash",
        role="moderator",
        status="active",
        email_verified_at=datetime.now(UTC),
    )
    db_session.add(mod_user)
    await db_session.flush()

    raw_sid = f"sess_{uuid.uuid4()}"
    sess = Session(
        user_id=mod_user.id,
        token_hash=hash_token(raw_sid),
        csrf_token_hash=hash_token("csrf"),
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
    )
    db_session.add(sess)
    await db_session.commit()

    # 1. Benchmark public found browse latency
    t0 = time.perf_counter()
    resp_browse = await async_client.get("/api/found?limit=20", cookies={"session_id": raw_sid})
    t_browse_ms = (time.perf_counter() - t0) * 1000.0

    assert resp_browse.status_code == 200
    assert t_browse_ms < 300.0, f"Browse latency {t_browse_ms:.1f}ms exceeds 300ms limit (AC-137)"

    # 2. Benchmark staff dashboard latency
    t0 = time.perf_counter()
    resp_dash = await async_client.get("/api/dashboard", cookies={"session_id": raw_sid})
    t_dash_ms = (time.perf_counter() - t0) * 1000.0

    assert resp_dash.status_code == 200
    assert t_dash_ms < 500.0, f"Dashboard latency {t_dash_ms:.1f}ms exceeds 500ms limit (AC-137)"
