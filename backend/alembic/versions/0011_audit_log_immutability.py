"""audit_log_immutability

Revision ID: 0011_audit_immutability
Revises: 0010_handover_table
Create Date: 2026-10-20 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '0011_audit_immutability'
down_revision: str | None = '0010_handover_table'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # AC-97 & AC-102: Trigger enforcing append-only audit_log unless app.allow_retention_purge is 'true'
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_log_immutable_trigger()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                RAISE EXCEPTION 'audit_log is append-only: updates are prohibited';
            ELSIF TG_OP = 'DELETE' THEN
                IF current_setting('app.allow_retention_purge', true) = 'true' THEN
                    RETURN OLD;
                ELSE
                    RAISE EXCEPTION 'audit_log is append-only: deletes are prohibited';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_audit_log_immutable ON audit_log;
        CREATE TRIGGER trg_audit_log_immutable
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW
        EXECUTE FUNCTION audit_log_immutable_trigger();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_immutable ON audit_log;")
    op.execute("DROP FUNCTION IF EXISTS audit_log_immutable_trigger();")
