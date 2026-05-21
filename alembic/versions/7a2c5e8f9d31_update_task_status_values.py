"""update task status values

Revision ID: 7a2c5e8f9d31
Revises: d25a2ba4c85c
Create Date: 2026-05-21 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "7a2c5e8f9d31"
down_revision: Union[str, Sequence[str], None] = "d25a2ba4c85c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "CREATE TYPE taskstatus_new AS ENUM "
        "('Pending', 'Completed', 'Failed', 'Approved', 'Rejected', 'Expired')"
    )
    op.execute(
        """
        ALTER TABLE tasks
        ALTER COLUMN status TYPE taskstatus_new
        USING (
            CASE status::text
                WHEN 'InProgress' THEN 'Pending'
                WHEN 'Cancelled' THEN 'Rejected'
                ELSE status::text
            END
        )::taskstatus_new
        """
    )
    op.execute("DROP TYPE taskstatus")
    op.execute("ALTER TYPE taskstatus_new RENAME TO taskstatus")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        "CREATE TYPE taskstatus_old AS ENUM "
        "('Pending', 'InProgress', 'Completed', 'Cancelled')"
    )
    op.execute(
        """
        ALTER TABLE tasks
        ALTER COLUMN status TYPE taskstatus_old
        USING (
            CASE status::text
                WHEN 'Failed' THEN 'Cancelled'
                WHEN 'Approved' THEN 'Completed'
                WHEN 'Rejected' THEN 'Cancelled'
                WHEN 'Expired' THEN 'Cancelled'
                ELSE status::text
            END
        )::taskstatus_old
        """
    )
    op.execute("DROP TYPE taskstatus")
    op.execute("ALTER TYPE taskstatus_old RENAME TO taskstatus")
