"""Create reports and item images tables

Revision ID: 0004_reports_and_photos
Revises: 0003_campus_locations
Create Date: 2026-10-19 15:30:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0004_reports_and_photos"
down_revision: str | None = "0003_campus_locations"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # 1. item_reports table
    op.create_table(
        "item_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("type", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=25), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("private_details", sa.Text(), nullable=True),
        sa.Column("verification_prompts", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("time_precision", sa.String(length=20), nullable=False),
        sa.Column(
            "location_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campus_locations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "reporter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("disposition", sa.String(length=50), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "reviewed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_item_reports_status", "item_reports", ["status"])
    op.create_index("ix_item_reports_category", "item_reports", ["category"])
    op.create_index("ix_item_reports_window_start", "item_reports", ["window_start"])
    op.create_index("ix_item_reports_window_end", "item_reports", ["window_end"])
    op.create_index("ix_item_reports_location_id", "item_reports", ["location_id"])
    op.create_index("ix_item_reports_reporter_id", "item_reports", ["reporter_id"])
    op.create_index("ix_item_reports_created_at", "item_reports", ["created_at"])
    op.create_index("ix_item_reports_type_status", "item_reports", ["type", "status"])

    # 2. item_images table
    op.create_table(
        "item_images",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("item_reports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("storage_key", sa.String(length=100), nullable=False),
        sa.Column("original_mime", sa.String(length=50), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("dhash", sa.String(length=16), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("is_public", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("moderation_status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_item_images_report_id", "item_images", ["report_id"])
    op.create_index("ix_item_images_storage_key", "item_images", ["storage_key"], unique=True)
    op.create_index("ix_item_images_dhash", "item_images", ["dhash"])


def downgrade() -> None:
    op.drop_table("item_images")
    op.drop_table("item_reports")
