"""hnsw_indexes

Revision ID: 0008_hnsw_indexes
Revises: 0007_match_candidates
Create Date: 2026-10-19 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008_hnsw_indexes"
down_revision: Union[str, None] = "0007_match_candidates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # AC-66 & D-08: HNSW vector indexes for cosine similarity
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_text_embeddings_hnsw ON text_embeddings USING hnsw (vector vector_cosine_ops);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_image_embeddings_hnsw ON image_embeddings USING hnsw (vector vector_cosine_ops);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_image_embeddings_hnsw;")
    op.execute("DROP INDEX IF EXISTS ix_text_embeddings_hnsw;")
