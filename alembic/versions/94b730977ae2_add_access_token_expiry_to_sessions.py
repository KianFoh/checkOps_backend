"""add access token expiry to sessions

Revision ID: 94b730977ae2
Revises: 1ef91f7d5a4b
Create Date: 2026-05-19 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "94b730977ae2"
down_revision: Union[str, Sequence[str], None] = "1ef91f7d5a4b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("access_token_expires_at", sa.DateTime(), nullable=True))
    op.execute("UPDATE sessions SET access_token_expires_at = expires_at WHERE access_token_expires_at IS NULL")
    op.alter_column("sessions", "access_token_expires_at", nullable=False)


def downgrade() -> None:
    op.drop_column("sessions", "access_token_expires_at")
