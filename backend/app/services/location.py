import uuid
from typing import Any, cast

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
    db: AsyncSession, location_id: uuid.UUID | None
) -> tuple[uuid.UUID | None, str | None]:
    """Walk up the ancestor tree to find the nearest ancestor (or self) where kind == 'building'.

    Returns (building_id, building_name) or (None, None), also for a report that only has a
    typed place (D-22); that text is private and never used here.
    """
    if location_id is None:
        return None, None
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
    db: AsyncSession, location_ids: list[uuid.UUID | None]
) -> dict[uuid.UUID | None, tuple[uuid.UUID | None, str | None]]:
    """Batch resolve building-level location for multiple locations (None means no building)."""
    unique_ids = list({i for i in location_ids if i is not None})
    if not unique_ids:
        return {}

    mapping: dict[uuid.UUID | None, tuple[uuid.UUID | None, str | None]] = {}
    for loc_id in unique_ids:
        b_id, b_name = await resolve_building_for_location(db, loc_id)
        mapping[loc_id] = (b_id, b_name)
    return mapping


async def calculate_db_location_score(
    db: AsyncSession, loc_a_id: uuid.UUID | None, loc_b_id: uuid.UUID | None
) -> float | None:
    """Calculate location similarity score between two locations in the database."""
    if loc_a_id is None or loc_b_id is None:
        return None
    if loc_a_id == loc_b_id:
        return 1.0

    from sqlalchemy import select

    from app.domain.location import LocationNode, calculate_location_score
    from app.models.location import CampusLocation, LocationAdjacency

    locs_res = await db.execute(select(CampusLocation))
    all_locs = {loc.id: loc for loc in locs_res.scalars().all()}
    if loc_a_id not in all_locs or loc_b_id not in all_locs:
        return None

    adj_res = await db.execute(select(LocationAdjacency))
    adjacency_set = {(adj.building_a, adj.building_b) for adj in adj_res.scalars().all()}
    for a, b in list(adjacency_set):
        adjacency_set.add((b, a))

    node_map: dict[uuid.UUID, LocationNode] = {}

    def get_or_create_node(lid: uuid.UUID) -> LocationNode | None:
        if lid in node_map:
            return node_map[lid]
        loc = all_locs.get(lid)
        if loc is None:
            return None
        parent_node = get_or_create_node(loc.parent_id) if loc.parent_id else None
        node = LocationNode(id=loc.id, name=loc.name, kind=cast(Any, loc.kind), parent=parent_node)
        node_map[lid] = node
        return node

    node_a = get_or_create_node(loc_a_id)
    node_b = get_or_create_node(loc_b_id)
    return calculate_location_score(node_a, node_b, adjacency_set)
