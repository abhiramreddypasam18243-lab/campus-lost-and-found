"""Initial schema and pgvector extension

Revision ID: 0001_initial
Revises: 
Create Date: 2026-10-19 13:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable the pgvector extension for vector embeddings
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")


def downgrade() -> None:
    # Drop vector extension on full downgrade
    op.execute("DROP EXTENSION IF EXISTS vector;")
