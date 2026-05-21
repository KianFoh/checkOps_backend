"""add task description

Revision ID: 3f6b8c9d2a10
Revises: 7a2c5e8f9d31
Create Date: 2026-05-21 20:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3f6b8c9d2a10"
down_revision: Union[str, Sequence[str], None] = "7a2c5e8f9d31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("tasks", sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("tasks", "description")
