import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def write_audit_log(
    db: AsyncSession,
    actor_id: uuid.UUID | None,
    role: str,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    summary: dict[str, Any] | None = None,
) -> AuditLog:
    """Write an immutable audit log entry in the current transaction."""
    entry = AuditLog(
        actor_id=actor_id,
        role=role,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary or {},
    )
    db.add(entry)
    return entry
