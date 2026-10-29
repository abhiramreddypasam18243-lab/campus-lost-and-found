"""Database seed script for demo journey and synthetic campus data (AC-145)."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.embeddings import ModelRegistry
from app.models.location import CampusLocation, LocationAdjacency
from app.models.report import ItemReport
from app.models.user import User
from app.services.job_queue import enqueue_job


async def seed_data(session: AsyncSession) -> None:
    now = datetime.now(UTC)

    # 1. Seed Model Registry
    settings = get_settings()
    models_to_seed = [
        ("text", settings.TEXT_MODEL_NAME, settings.TEXT_MODEL_VERSION, 384),
        ("image", settings.CLIP_MODEL_NAME, settings.CLIP_MODEL_VERSION, 512),
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
        # Exactly one active version per model type: the pinned one from settings.
        others = (
            (
                await session.execute(
                    select(ModelRegistry).where(
                        ModelRegistry.model_type == m_type, ModelRegistry.is_active.is_(True)
                    )
                )
            )
            .scalars()
            .all()
        )
        for other in others:
            other.is_active = other is existing
        if not existing:
            reg = ModelRegistry(
                model_type=m_type,
                model_name=m_name,
                model_version=m_ver,
                dimension=dim,
                is_active=True,
            )
            session.add(reg)
        else:
            existing.is_active = True

    # 2. Seed Campus Locations
    locations_tree = [
        (
            "Library",
            "building",
            Decimal("12.971"),
            Decimal("77.594"),
            [
                ("Library - Floor 1", "floor"),
                ("Library - Floor 2", "floor"),
            ],
        ),
        (
            "Science Block",
            "building",
            Decimal("12.972"),
            Decimal("77.595"),
            [
                ("Science Block - Floor 1", "floor"),
                ("Science Block - Lab 101", "room"),
            ],
        ),
        (
            "Engineering Center",
            "building",
            Decimal("12.973"),
            Decimal("77.596"),
            [
                ("Engineering - Lab A", "room"),
                ("Engineering - Lab B", "room"),
            ],
        ),
        (
            "Student Union",
            "building",
            Decimal("12.970"),
            Decimal("77.593"),
            [
                ("Cafeteria Area", "area"),
            ],
        ),
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

    # Optional personal admin, configured only through the environment (never committed).
    seed_admin_email = os.environ.get("SEED_ADMIN_EMAIL", "").strip().lower()
    seed_admin_password = os.environ.get("SEED_ADMIN_PASSWORD", "")
    if seed_admin_email and seed_admin_password:
        users_to_seed.append((seed_admin_email, seed_admin_password, "Administrator", "admin"))

    user_map: dict[str, User] = {}
    for email, raw_pw, display_name, role in users_to_seed:
        u = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
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
            6,
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
            6,
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
            6,
        ),
        (
            "lost",
            "open",
            "Black Sony Wireless Earbuds Case (Synthetic Demo Item)",
            "Small black charging case for wireless earbuds, scratched lid, one earbud may be missing.",
            "earphones",
            user_map["student2@campus.edu"].id,
            location_map["Science Block - Lab 101"].id,
            ["Which brand is printed on the case?", "Is there a sticker or a keyring on it?"],
            20,
        ),
        (
            "lost",
            "open",
            "Grey Hoodie with Zip (Synthetic Demo Item)",
            "Grey zip-up hoodie, size M, white drawstrings and a small ink stain on the left cuff.",
            "clothing",
            user_map["student1@campus.edu"].id,
            location_map["Cafeteria Area"].id,
            ["What size is it?", "Where is the ink stain?"],
            30,
        ),
        (
            "lost",
            "open",
            "Silver Casio Calculator (Synthetic Demo Item)",
            "Scientific calculator in a silver case, initials scratched on the back.",
            "other",
            user_map["student1@campus.edu"].id,
            location_map["Engineering - Lab B"].id,
            ["Which initials are scratched on the back?"],
            48,
        ),
        (
            "lost",
            "open",
            "Brown Leather Keychain with Three Keys (Synthetic Demo Item)",
            "Brown leather keychain holding three brass keys and a small blue bottle opener.",
            "keys",
            user_map["student2@campus.edu"].id,
            location_map["Library"].id,
            ["How many keys are on the ring?", "What else hangs from the keychain?"],
            10,
        ),
        (
            "lost",
            "open",
            "Green Backpack with Laptop Sleeve (Synthetic Demo Item)",
            "Dark green backpack with a padded laptop sleeve, a keyring badge on the zip and a physics notebook inside.",
            "bag",
            user_map["student1@campus.edu"].id,
            location_map["Library - Floor 2"].id,
            ["What badge hangs from the zip?", "What subject is the notebook?"],
            3,
        ),
        (
            "lost",
            "open",
            "Phone in a Clear Case with Pressed Flowers (Synthetic Demo Item)",
            "Phone with a clear case showing pressed dried flowers behind it, cracked top-left corner of the screen.",
            "phone",
            user_map["student2@campus.edu"].id,
            location_map["Student Union"].id,
            ["What is behind the clear case?", "Which corner of the screen is cracked?"],
            26,
        ),
        (
            "found",
            "open",
            "Set of Brass Keys on a Leather Strap (Synthetic Demo Item)",
            "Three brass keys on a brown leather strap with a small blue bottle opener, left on a reading table.",
            "keys",
            user_map["student1@campus.edu"].id,
            location_map["Library - Floor 1"].id,
            ["How many keys are on the ring?"],
            8,
        ),
        (
            "found",
            "open",
            "Grey Zip Sweatshirt (Synthetic Demo Item)",
            "Grey zip sweatshirt with white drawstrings, left on a chair near the counter.",
            "clothing",
            user_map["student2@campus.edu"].id,
            location_map["Cafeteria Area"].id,
            ["What size is it?"],
            28,
        ),
    ]

    for r_type, r_status, title, desc, cat, rep_id, loc_id, prompts, hours_ago in demo_reports:
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
                window_start=now - timedelta(hours=hours_ago),
                window_end=now - timedelta(hours=max(hours_ago - 1, 0)),
            )
            session.add(rep)
            await session.flush()
            await enqueue_job(session, kind="embed_report_text", entity_id=rep.id)

    await session.commit()
    print("Seed data successfully applied!")


async def main() -> None:
    async with AsyncSessionLocal() as session:
        await seed_data(session)


if __name__ == "__main__":
    asyncio.run(main())
