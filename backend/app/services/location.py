import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_descendant_location_ids(db: AsyncSession, root_id: uuid.UUID) -> list[uuid.UUID]:
    """Retrieve all descendant location UUIDs for a given root location (inclusive) using recursive CTE."""
    query = text(
        """
        WITH RECURSIVE sublocations AS (
            SELECT id FROM campus_locations WHERE id = :root_id
            UNION ALL
            SELECT cl.id FROM campus_locations cl
            JOIN sublocations sl ON cl.parent_id = sl.id
        )
        SELECT id FROM sublocations;
        """
    )
    result = await db.execute(query, {"root_id": root_id})
    return [row[0] for row in result.fetchall()]


async def resolve_building_for_location(
    db: AsyncSession, location_id: uuid.UUID
) -> tuple[uuid.UUID | None, str | None]:
    """Walk up the ancestor tree to find the nearest ancestor (or self) where kind == 'building'.

    Returns (building_id, building_name) or (None, None).
    """
    query = text(
        """
        WITH RECURSIVE ancestors AS (
            SELECT id, parent_id, kind, name, 0 as depth
            FROM campus_locations
            WHERE id = :location_id
            UNION ALL
            SELECT cl.id, cl.parent_id, cl.kind, cl.name, a.depth + 1
            FROM campus_locations cl
            JOIN ancestors a ON cl.id = a.parent_id
        )
        SELECT id, name FROM ancestors
        WHERE kind = 'building'
        ORDER BY depth ASC
        LIMIT 1;
        """
    )
    result = await db.execute(query, {"location_id": location_id})
    row = result.fetchone()
    if row is not None:
        return row[0], row[1]
    return None, None


async def resolve_buildings_batch(
    db: AsyncSession, location_ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[uuid.UUID | None, str | None]]:
    """Batch resolve building-level location for multiple locations."""
    if not location_ids:
        return {}

    unique_ids = list(set(location_ids))
    mapping: dict[uuid.UUID, tuple[uuid.UUID | None, str | None]] = {}
    for loc_id in unique_ids:
        b_id, b_name = await resolve_building_for_location(db, loc_id)
        mapping[loc_id] = (b_id, b_name)
    return mapping
