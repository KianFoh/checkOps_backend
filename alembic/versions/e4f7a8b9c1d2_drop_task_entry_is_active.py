"""drop task entry is active

Revision ID: e4f7a8b9c1d2
Revises: d5f9a1b2c3e4
Create Date: 2026-05-21 21:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e4f7a8b9c1d2"
down_revision: Union[str, Sequence[str], None] = "d5f9a1b2c3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column("task_entries", "is_active")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "task_entries",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column("task_entries", "is_active", server_default=None)
