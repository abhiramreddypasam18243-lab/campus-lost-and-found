"""worker_heartbeats

Revision ID: 0012_worker_heartbeats
Revises: 0011_audit_immutability
Create Date: 2026-10-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0012_worker_heartbeats'
down_revision: Union[str, None] = '0011_audit_immutability'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'worker_heartbeats',
        sa.Column('worker_id', sa.String(length=100), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('worker_id'),
    )


def downgrade() -> None:
    op.drop_table('worker_heartbeats')
