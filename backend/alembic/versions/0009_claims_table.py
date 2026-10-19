"""claims_table

Revision ID: 0009_claims_table
Revises: 0008_hnsw_indexes
Create Date: 2026-10-19 23:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0009_claims_table'
down_revision: Union[str, None] = '0008_hnsw_indexes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'claims',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('found_id', sa.UUID(), nullable=False),
        sa.Column('lost_id', sa.UUID(), nullable=True),
        sa.Column('claimant_id', sa.UUID(), nullable=False),
        sa.Column('evidence', sa.Text(), nullable=False),
        sa.Column('answers', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('image_ids', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('decision_note', sa.Text(), nullable=True),
        sa.Column('reviewer_id', sa.UUID(), nullable=True),
        sa.Column('locked_by_id', sa.UUID(), nullable=True),
        sa.Column('lock_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['claimant_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['found_id'], ['item_reports.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['lost_id'], ['item_reports.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['locked_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_claims_claimant_id'), 'claims', ['claimant_id'], unique=False)
    op.create_index(op.f('ix_claims_found_id'), 'claims', ['found_id'], unique=False)
    op.create_index(op.f('ix_claims_lost_id'), 'claims', ['lost_id'], unique=False)
    op.create_index(op.f('ix_claims_status'), 'claims', ['status'], unique=False)
    op.create_index(op.f('ix_claims_submitted_at'), 'claims', ['submitted_at'], unique=False)
    op.create_index('ix_claims_claimant_status', 'claims', ['claimant_id', 'status'], unique=False)
    op.create_index('ix_claims_found_status', 'claims', ['found_id', 'status'], unique=False)
    op.create_index('ix_claims_status_submitted_at', 'claims', ['status', 'submitted_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_claims_status_submitted_at', table_name='claims')
    op.drop_index('ix_claims_found_status', table_name='claims')
    op.drop_index('ix_claims_claimant_status', table_name='claims')
    op.drop_index(op.f('ix_claims_submitted_at'), table_name='claims')
    op.drop_index(op.f('ix_claims_status'), table_name='claims')
    op.drop_index(op.f('ix_claims_lost_id'), table_name='claims')
    op.drop_index(op.f('ix_claims_found_id'), table_name='claims')
    op.drop_index(op.f('ix_claims_claimant_id'), table_name='claims')
    op.drop_table('claims')
