"""match_candidates

Revision ID: 0007_match_candidates
Revises: 0006_jobs_embed_notifs
Create Date: 2026-10-19 16:06:50.047219

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0007_match_candidates'
down_revision: Union[str, None] = '0006_jobs_embed_notifs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('match_candidates',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('lost_id', sa.UUID(), nullable=False),
        sa.Column('found_id', sa.UUID(), nullable=False),
        sa.Column('text_score', sa.Float(), nullable=True),
        sa.Column('image_score', sa.Float(), nullable=True),
        sa.Column('location_score', sa.Float(), nullable=True),
        sa.Column('time_score', sa.Float(), nullable=True),
        sa.Column('combined_score', sa.Float(), nullable=False),
        sa.Column('bin', sa.String(length=20), nullable=False),
        sa.Column('weights_version', sa.String(length=50), nullable=False),
        sa.Column('model_versions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('explanation', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['found_id'], ['item_reports.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['lost_id'], ['item_reports.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('lost_id', 'found_id', 'weights_version', name='uq_match_candidates_pair_weights')
    )
    op.create_index(op.f('ix_match_candidates_bin'), 'match_candidates', ['bin'], unique=False)
    op.create_index(op.f('ix_match_candidates_combined_score'), 'match_candidates', ['combined_score'], unique=False)
    op.create_index(op.f('ix_match_candidates_created_at'), 'match_candidates', ['created_at'], unique=False)
    op.create_index(op.f('ix_match_candidates_found_id'), 'match_candidates', ['found_id'], unique=False)
    op.create_index('ix_match_candidates_found_status', 'match_candidates', ['found_id', 'status'], unique=False)
    op.create_index(op.f('ix_match_candidates_lost_id'), 'match_candidates', ['lost_id'], unique=False)
    op.create_index('ix_match_candidates_lost_status', 'match_candidates', ['lost_id', 'status'], unique=False)
    op.create_index(op.f('ix_match_candidates_status'), 'match_candidates', ['status'], unique=False)

    op.create_table('match_feedback',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('candidate_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['candidate_id'], ['match_candidates.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_match_feedback_candidate_id'), 'match_feedback', ['candidate_id'], unique=False)
    op.create_index(op.f('ix_match_feedback_created_at'), 'match_feedback', ['created_at'], unique=False)
    op.create_index(op.f('ix_match_feedback_user_id'), 'match_feedback', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_match_feedback_user_id'), table_name='match_feedback')
    op.drop_index(op.f('ix_match_feedback_created_at'), table_name='match_feedback')
    op.drop_index(op.f('ix_match_feedback_candidate_id'), table_name='match_feedback')
    op.drop_table('match_feedback')
    op.drop_index(op.f('ix_match_candidates_status'), table_name='match_candidates')
    op.drop_index('ix_match_candidates_lost_status', table_name='match_candidates')
    op.drop_index(op.f('ix_match_candidates_lost_id'), table_name='match_candidates')
    op.drop_index('ix_match_candidates_found_status', table_name='match_candidates')
    op.drop_index(op.f('ix_match_candidates_found_id'), table_name='match_candidates')
    op.drop_index(op.f('ix_match_candidates_created_at'), table_name='match_candidates')
    op.drop_index(op.f('ix_match_candidates_combined_score'), table_name='match_candidates')
    op.drop_index(op.f('ix_match_candidates_bin'), table_name='match_candidates')
    op.drop_table('match_candidates')
