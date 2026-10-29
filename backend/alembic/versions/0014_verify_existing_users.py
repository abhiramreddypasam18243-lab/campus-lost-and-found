"""verify existing accounts (D-25)

Revision ID: 0014_verify_existing_users
Revises: 0013_report_location_text
Create Date: 2026-10-29 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = '0014_verify_existing_users'
down_revision: Union[str, None] = '0013_report_location_text'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The emailed code is gone, so nobody can be left waiting on one.
    op.execute("UPDATE users SET email_verified_at = now() WHERE email_verified_at IS NULL")


def downgrade() -> None:
    # Data-only change; which accounts were unverified is not recoverable.
    pass
