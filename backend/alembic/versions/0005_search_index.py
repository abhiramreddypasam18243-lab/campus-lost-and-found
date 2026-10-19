"""Add GIN full text search index on item_reports title and description

Revision ID: 0005_search_index
Revises: 0004_reports_and_photos
Create Date: 2026-10-19 16:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_search_index"
down_revision: str | None = "0004_reports_and_photos"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_item_reports_fts ON item_reports USING gin(to_tsvector('english', title || ' ' || description));"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_item_reports_fts;")
