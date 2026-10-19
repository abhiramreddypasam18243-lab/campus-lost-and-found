"""Create campus locations and adjacency tables

Revision ID: 0003_campus_locations
Revises: 0002_auth_and_audit
Create Date: 2026-10-19 14:35:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003_campus_locations"
down_revision: str | None = "0002_auth_and_audit"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # 1. campus_locations table
    op.create_table(
        "campus_locations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campus_locations.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("lat", sa.Numeric(precision=8, scale=3), nullable=True),
        sa.Column("lng", sa.Numeric(precision=8, scale=3), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('campus', 'building', 'floor', 'room', 'area')",
            name="ck_campus_locations_kind",
        ),
    )
    op.create_index(
        "ix_campus_locations_parent_id",
        "campus_locations",
        ["parent_id"],
    )
    # Expression index for sibling case-insensitive uniqueness
    op.execute(
        """
        CREATE UNIQUE INDEX uq_locations_parent_name_ci 
        ON campus_locations (COALESCE(parent_id, '00000000-0000-0000-0000-000000000000'::uuid), lower(name));
        """
    )

    # 2. location_adjacency table
    op.create_table(
        "location_adjacency",
        sa.Column(
            "building_a",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campus_locations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "building_b",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campus_locations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("building_a", "building_b"),
        sa.CheckConstraint("building_a != building_b", name="ck_location_adjacency_distinct"),
    )


def downgrade() -> None:
    op.drop_table("location_adjacency")
    op.execute("DROP INDEX IF EXISTS uq_locations_parent_name_ci;")
    op.drop_index("ix_campus_locations_parent_id", table_name="campus_locations")
    op.drop_table("campus_locations")
