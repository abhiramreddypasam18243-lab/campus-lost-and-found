"""Database seed script for demo journey and synthetic campus data (AC-145)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.embeddings import ModelRegistry
from app.models.location import CampusLocation, LocationAdjacency
from app.models.report import ItemReport
from app.models.user import User


async def seed_data(session: AsyncSession) -> None:
    now = datetime.now(UTC)

    # 1. Seed Model Registry
    models_to_seed = [
        ("text", "all-MiniLM-L6-v2", "v1", 384),
        ("image", "clip-ViT-B-32", "v1", 512),
    ]
    for m_type, m_name, m_ver, dim in models_to_seed:
        existing = (
            await session.execute(
                select(ModelRegistry).where(
                    ModelRegistry.model_type == m_type,
                    ModelRegistry.model_name == m_name,
                    ModelRegistry.model_version == m_ver,
                )
            )
        ).scalar_one_or_none()
        if not existing:
            reg = ModelRegistry(
                model_type=m_type,
                model_name=m_name,
                model_version=m_ver,
                dimension=dim,
                is_active=True,
            )
            session.add(reg)

    # 2. Seed Campus Locations
    locations_tree = [
        ("Library", "building", Decimal("12.971"), Decimal("77.594"), [
            ("Library - Floor 1", "floor"),
            ("Library - Floor 2", "floor"),
        ]),
        ("Science Block", "building", Decimal("12.972"), Decimal("77.595"), [
            ("Science Block - Floor 1", "floor"),
            ("Science Block - Lab 101", "room"),
        ]),
        ("Engineering Center", "building", Decimal("12.973"), Decimal("77.596"), [
            ("Engineering - Lab A", "room"),
            ("Engineering - Lab B", "room"),
        ]),
        ("Student Union", "building", Decimal("12.970"), Decimal("77.593"), [
            ("Cafeteria Area", "area"),
        ]),
    ]

    location_map: dict[str, CampusLocation] = {}
    for b_name, b_kind, b_lat, b_lng, children in locations_tree:
        bldg = (
            await session.execute(select(CampusLocation).where(CampusLocation.name == b_name))
        ).scalar_one_or_none()
        if not bldg:
            bldg = CampusLocation(name=b_name, kind=b_kind, lat=b_lat, lng=b_lng)
            session.add(bldg)
            await session.flush()
        location_map[b_name] = bldg

        for c_name, c_kind in children:
            child = (
                await session.execute(select(CampusLocation).where(CampusLocation.name == c_name))
            ).scalar_one_or_none()
            if not child:
                child = CampusLocation(name=c_name, kind=c_kind, parent_id=bldg.id)
                session.add(child)
                await session.flush()
            location_map[c_name] = child

    # Seed Adjacency between Library and Science Block
    lib_bldg = location_map["Library"]
    sci_bldg = location_map["Science Block"]
    adj_existing = (
        await session.execute(
            select(LocationAdjacency).where(
                (
                    (LocationAdjacency.building_a == lib_bldg.id)
                    & (LocationAdjacency.building_b == sci_bldg.id)
                )
                | (
                    (LocationAdjacency.building_a == sci_bldg.id)
                    & (LocationAdjacency.building_b == lib_bldg.id)
                )
            )
        )
    ).scalar_one_or_none()
    if not adj_existing:
        session.add(LocationAdjacency(building_a=lib_bldg.id, building_b=sci_bldg.id))

    # 3. Seed Users for each role
    users_to_seed = [
        ("admin@campus.edu", "CampusAdmin2026!", "Campus Administrator", "admin"),
        ("moderator@campus.edu", "CampusMod2026!", "Staff Moderator", "moderator"),
        ("student1@campus.edu", "StudentPass2026!", "Alice Student", "user"),
        ("student2@campus.edu", "StudentPass2026!", "Bob Student", "user"),
    ]

    user_map: dict[str, User] = {}
    for email, raw_pw, display_name, role in users_to_seed:
        u = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if not u:
            u = User(
                email=email,
                password_hash=hash_password(raw_pw),
                display_name=display_name,
                role=role,
                status="active",
                email_verified_at=now,
            )
            session.add(u)
            await session.flush()
        user_map[email] = u

    # 4. Seed Demo Reports
    leaf_loc = location_map["Library - Floor 1"]
    demo_reports = [
        (
            "lost",
            "open",
            "Navy Blue HydroFlask (Synthetic Demo Item)",
            "32oz dark blue insulated flask with a slight dent on the base and stickers.",
            "bottle",
            user_map["student1@campus.edu"].id,
            leaf_loc.id,
            ["What color is the cap?", "Are there stickers on it?"],
        ),
        (
            "found",
            "open",
            "Dark Blue Water Bottle (Synthetic Demo Item)",
            "Found metal vacuum flask on desk in library reading area.",
            "bottle",
            user_map["student2@campus.edu"].id,
            leaf_loc.id,
            ["What color is the cap?", "Are there stickers on it?"],
        ),
        (
            "found",
            "open",
            "Black Dell 65W Laptop Charger (Synthetic Demo Item)",
            "USB-C power supply adapter found plugged in at table 4.",
            "laptop_tablet",
            user_map["student2@campus.edu"].id,
            location_map["Engineering - Lab A"].id,
            ["What is the output wattage?"],
        ),
    ]

    for r_type, r_status, title, desc, cat, rep_id, loc_id, prompts in demo_reports:
        existing_report = (
            await session.execute(select(ItemReport).where(ItemReport.title == title))
        ).scalar_one_or_none()
        if not existing_report:
            rep = ItemReport(
                type=r_type,
                status=r_status,
                title=title,
                description=desc,
                category=cat,
                location_id=loc_id,
                reporter_id=rep_id,
                verification_prompts=prompts,
                time_precision="hour",
                window_start=now - timedelta(hours=6),
                window_end=now - timedelta(hours=5),
            )
            session.add(rep)

    await session.commit()
    print("Seed data successfully applied!")


async def main() -> None:
    async with AsyncSessionLocal() as session:
        await seed_data(session)


if __name__ == "__main__":
    asyncio.run(main())
