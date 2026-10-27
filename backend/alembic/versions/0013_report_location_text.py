"""report location_text (D-22)

Revision ID: 0013_report_location_text
Revises: 0012_worker_heartbeats
Create Date: 2026-10-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0013_report_location_text'
down_revision: Union[str, None] = '0012_worker_heartbeats'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('item_reports', sa.Column('location_text', sa.String(length=200), nullable=True))
    op.alter_column('item_reports', 'location_id', existing_type=sa.UUID(), nullable=True)
    op.create_check_constraint(
        'ck_item_reports_has_location',
        'item_reports',
        'location_id IS NOT NULL OR location_text IS NOT NULL',
    )


def downgrade() -> None:
    # Reports that only have a typed place cannot satisfy NOT NULL again; refuse rather than guess.
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM item_reports WHERE location_id IS NULL) THEN "
        "RAISE EXCEPTION 'reports without a campus location exist; reassign them before downgrading'; "
        "END IF; END $$"
    )
    op.drop_constraint('ck_item_reports_has_location', 'item_reports', type_='check')
    op.alter_column('item_reports', 'location_id', existing_type=sa.UUID(), nullable=False)
    op.drop_column('item_reports', 'location_text')
