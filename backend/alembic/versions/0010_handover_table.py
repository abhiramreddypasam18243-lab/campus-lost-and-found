"""handover_table

Revision ID: 0010_handover_table
Revises: 0009_claims_table
Create Date: 2026-10-19 23:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0010_handover_table'
down_revision: Union[str, None] = '0009_claims_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'handovers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('claim_id', sa.UUID(), nullable=False),
        sa.Column('code_hmac', sa.String(length=64), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('max_attempts', sa.Integer(), nullable=False),
        sa.Column('reissue_count', sa.Integer(), nullable=False),
        sa.Column('max_reissues', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('issued_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('verified_by_id', sa.UUID(), nullable=True),
        sa.Column('identity_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['claim_id'], ['claims.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['verified_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('claim_id', name='uq_handovers_claim_id')
    )
    op.create_index(op.f('ix_handovers_claim_id'), 'handovers', ['claim_id'], unique=False)
    op.create_index(op.f('ix_handovers_expires_at'), 'handovers', ['expires_at'], unique=False)
    op.create_index(op.f('ix_handovers_status'), 'handovers', ['status'], unique=False)
    op.create_index('ix_handovers_status_expires_at', 'handovers', ['status', 'expires_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_handovers_status_expires_at', table_name='handovers')
    op.drop_index(op.f('ix_handovers_status'), table_name='handovers')
    op.drop_index(op.f('ix_handovers_expires_at'), table_name='handovers')
    op.drop_index(op.f('ix_handovers_claim_id'), table_name='handovers')
    op.drop_table('handovers')
