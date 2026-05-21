"""add task entry is active

Revision ID: d5f9a1b2c3e4
Revises: c8e7f2a4d9b1
Create Date: 2026-05-21 21:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d5f9a1b2c3e4"
down_revision: Union[str, Sequence[str], None] = "c8e7f2a4d9b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "task_entries",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column("task_entries", "is_active", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("task_entries", "is_active")
