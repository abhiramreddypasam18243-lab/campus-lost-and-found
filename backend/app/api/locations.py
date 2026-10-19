import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_role, verify_csrf
from app.core.database import get_db
from app.models.location import CampusLocation, LocationAdjacency
from app.models.user import User
from app.schemas.location import (
    AdjacencyCreate,
    AdjacencyResponse,
    LocationCreate,
    LocationResponse,
    LocationUpdate,
)
from app.services.audit import write_audit_log

router = APIRouter(prefix="/api/locations", tags=["locations"])


@router.get("", response_model=list[LocationResponse])
async def list_locations(
    db: AsyncSession = Depends(get_db),
) -> list[LocationResponse]:
    stmt = select(CampusLocation).order_by(CampusLocation.created_at)
    result = await db.execute(stmt)
    locations = result.scalars().all()
    return [
        LocationResponse(
            id=loc.id,
            parent_id=loc.parent_id,
            kind=loc.kind,
            name=loc.name,
            lat=float(loc.lat) if loc.lat is not None else None,
            lng=float(loc.lng) if loc.lng is not None else None,
            created_at=loc.created_at,
        )
        for loc in locations
    ]


# --- Static adjacency routes declared BEFORE /{location_id} parameter routes ---


@router.get("/adjacency", response_model=list[AdjacencyResponse])
async def list_adjacencies(
    db: AsyncSession = Depends(get_db),
) -> list[AdjacencyResponse]:
    stmt = select(LocationAdjacency)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [AdjacencyResponse(building_a=r.building_a, building_b=r.building_b) for r in rows]


@router.post(
    "/adjacency",
    response_model=AdjacencyResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("admin")), Depends(verify_csrf)],
)
async def add_adjacency(
    payload: AdjacencyCreate,
    db: AsyncSession = Depends(get_db),
) -> AdjacencyResponse:
    if payload.building_a == payload.building_b:
        raise HTTPException(
            status_code=422,
            detail="cannot_be_adjacent_to_self",
        )

    # Validate that both locations exist and are kind == 'building'
    b_stmt = select(CampusLocation).where(
        CampusLocation.id.in_([payload.building_a, payload.building_b]),
    )
    b_res = await db.execute(b_stmt)
    bldgs = b_res.scalars().all()
    if len(bldgs) != 2:
        raise HTTPException(
            status_code=422,
            detail="both_nodes_must_exist",
        )
    for b in bldgs:
        if b.kind != "building":
            raise HTTPException(
                status_code=422,
                detail=f"location_{b.name}_is_not_a_building",
            )

    # Check if adjacency already exists in either direction
    existing_stmt = select(LocationAdjacency).where(
        or_(
            (LocationAdjacency.building_a == payload.building_a)
            & (LocationAdjacency.building_b == payload.building_b),
            (LocationAdjacency.building_a == payload.building_b)
            & (LocationAdjacency.building_b == payload.building_a),
        )
    )
    existing_res = await db.execute(existing_stmt)
    existing = existing_res.scalar_one_or_none()
    if existing is not None:
        return AdjacencyResponse(building_a=existing.building_a, building_b=existing.building_b)

    adj = LocationAdjacency(building_a=payload.building_a, building_b=payload.building_b)
    db.add(adj)
    await db.commit()
    return AdjacencyResponse(building_a=payload.building_a, building_b=payload.building_b)


@router.delete(
    "/adjacency/{building_a}/{building_b}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("admin")), Depends(verify_csrf)],
)
async def remove_adjacency(
    building_a: uuid.UUID,
    building_b: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    stmt = select(LocationAdjacency).where(
        or_(
            (LocationAdjacency.building_a == building_a)
            & (LocationAdjacency.building_b == building_b),
            (LocationAdjacency.building_a == building_b)
            & (LocationAdjacency.building_b == building_a),
        )
    )
    result = await db.execute(stmt)
    adj = result.scalar_one_or_none()
    if adj is not None:
        await db.delete(adj)
        await db.commit()


# --- Parameterized /{location_id} routes ---


@router.get("/{location_id}", response_model=LocationResponse)
async def get_location(
    location_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> LocationResponse:
    stmt = select(CampusLocation).where(CampusLocation.id == location_id)
    result = await db.execute(stmt)
    loc = result.scalar_one_or_none()
    if loc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="location_not_found")
    return LocationResponse(
        id=loc.id,
        parent_id=loc.parent_id,
        kind=loc.kind,
        name=loc.name,
        lat=float(loc.lat) if loc.lat is not None else None,
        lng=float(loc.lng) if loc.lng is not None else None,
        created_at=loc.created_at,
    )


@router.post(
    "",
    response_model=LocationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("admin")), Depends(verify_csrf)],
)
async def create_location(
    payload: LocationCreate,
    admin_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> LocationResponse:
    if payload.parent_id is not None:
        parent_stmt = select(CampusLocation).where(CampusLocation.id == payload.parent_id)
        parent_res = await db.execute(parent_stmt)
        if parent_res.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="parent_location_not_found"
            )

    # Check sibling name uniqueness (case-insensitive)
    sibling_stmt = select(CampusLocation).where(
        func.lower(CampusLocation.name) == payload.name.strip().lower(),
    )
    if payload.parent_id is not None:
        sibling_stmt = sibling_stmt.where(CampusLocation.parent_id == payload.parent_id)
    else:
        sibling_stmt = sibling_stmt.where(CampusLocation.parent_id.is_(None))

    sibling_res = await db.execute(sibling_stmt)
    if sibling_res.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="sibling_location_name_exists",
        )

    loc = CampusLocation(
        name=payload.name.strip(),
        kind=payload.kind,
        parent_id=payload.parent_id,
        lat=Decimal(str(payload.lat)) if payload.lat is not None else None,
        lng=Decimal(str(payload.lng)) if payload.lng is not None else None,
    )
    db.add(loc)
    await db.flush()

    await write_audit_log(
        db=db,
        actor_id=admin_user.id,
        role=admin_user.role,
        action="location.created",
        entity_type="campus_location",
        entity_id=loc.id,
        summary={"name": loc.name, "kind": loc.kind},
    )
    await db.commit()
    await db.refresh(loc)

    return LocationResponse(
        id=loc.id,
        parent_id=loc.parent_id,
        kind=loc.kind,
        name=loc.name,
        lat=float(loc.lat) if loc.lat is not None else None,
        lng=float(loc.lng) if loc.lng is not None else None,
        created_at=loc.created_at,
    )


@router.patch(
    "/{location_id}",
    response_model=LocationResponse,
    dependencies=[Depends(require_role("admin")), Depends(verify_csrf)],
)
async def update_location(
    location_id: uuid.UUID,
    payload: LocationUpdate,
    admin_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> LocationResponse:
    stmt = select(CampusLocation).where(CampusLocation.id == location_id)
    result = await db.execute(stmt)
    loc = result.scalar_one_or_none()
    if loc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="location_not_found")

    if payload.parent_id is not None:
        if payload.parent_id == location_id:
            raise HTTPException(
                status_code=422,
                detail="cannot_become_own_ancestor",
            )
        # Cycle detection: traverse ancestors of new parent to ensure location_id is not present
        curr_parent_id: uuid.UUID | None = payload.parent_id
        while curr_parent_id is not None:
            if curr_parent_id == location_id:
                raise HTTPException(
                    status_code=422,
                    detail="cannot_become_own_ancestor",
                )
            p_stmt = select(CampusLocation.parent_id).where(CampusLocation.id == curr_parent_id)
            p_res = await db.execute(p_stmt)
            curr_parent_id = p_res.scalar_one_or_none()

    target_parent_id = payload.parent_id if payload.parent_id is not None else loc.parent_id
    target_name = payload.name.strip() if payload.name is not None else loc.name

    # Sibling uniqueness check
    sibling_stmt = select(CampusLocation).where(
        CampusLocation.id != location_id,
        func.lower(CampusLocation.name) == target_name.lower(),
    )
    if target_parent_id is not None:
        sibling_stmt = sibling_stmt.where(CampusLocation.parent_id == target_parent_id)
    else:
        sibling_stmt = sibling_stmt.where(CampusLocation.parent_id.is_(None))

    sibling_res = await db.execute(sibling_stmt)
    if sibling_res.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="sibling_location_name_exists",
        )

    if payload.name is not None:
        loc.name = payload.name.strip()
    if payload.kind is not None:
        loc.kind = payload.kind
    if payload.parent_id is not None:
        loc.parent_id = payload.parent_id
    if payload.lat is not None:
        loc.lat = Decimal(str(payload.lat))
    if payload.lng is not None:
        loc.lng = Decimal(str(payload.lng))

    await write_audit_log(
        db=db,
        actor_id=admin_user.id,
        role=admin_user.role,
        action="location.updated",
        entity_type="campus_location",
        entity_id=loc.id,
        summary={"name": loc.name, "kind": loc.kind},
    )
    await db.commit()
    await db.refresh(loc)

    return LocationResponse(
        id=loc.id,
        parent_id=loc.parent_id,
        kind=loc.kind,
        name=loc.name,
        lat=float(loc.lat) if loc.lat is not None else None,
        lng=float(loc.lng) if loc.lng is not None else None,
        created_at=loc.created_at,
    )


@router.delete(
    "/{location_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("admin")), Depends(verify_csrf)],
)
async def delete_location(
    location_id: uuid.UUID,
    admin_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    stmt = select(CampusLocation).where(CampusLocation.id == location_id)
    result = await db.execute(stmt)
    loc = result.scalar_one_or_none()
    if loc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="location_not_found")

    # AC-17: Check if any item report uses this location
    table_check = await db.execute(
        text("SELECT 1 FROM information_schema.tables WHERE table_name = 'item_reports';")
    )
    if table_check.scalar_one_or_none() is not None:
        report_check = await db.execute(
            text("SELECT 1 FROM item_reports WHERE location_id = :loc_id LIMIT 1;"),
            {"loc_id": location_id},
        )
        if report_check.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="location_in_use_by_reports",
            )

    await write_audit_log(
        db=db,
        actor_id=admin_user.id,
        role=admin_user.role,
        action="location.deleted",
        entity_type="campus_location",
        entity_id=loc.id,
        summary={"name": loc.name},
    )
    await db.delete(loc)
    await db.commit()
