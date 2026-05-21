"""rename task entry scheduled at

Revision ID: c8e7f2a4d9b1
Revises: b6d4c2f1a9e0
Create Date: 2026-05-21 21:35:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c8e7f2a4d9b1"
down_revision: Union[str, Sequence[str], None] = "b6d4c2f1a9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("task_entries", "scheduled_at", new_column_name="start_at")


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("task_entries", "start_at", new_column_name="scheduled_at")
