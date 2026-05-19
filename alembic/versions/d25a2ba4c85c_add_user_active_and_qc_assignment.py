"""add user active and qc assignment

Revision ID: d25a2ba4c85c
Revises: 94b730977ae2
Create Date: 2026-05-19 15:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d25a2ba4c85c"
down_revision: Union[str, Sequence[str], None] = "94b730977ae2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("active", sa.Boolean(), nullable=True))
    op.execute("UPDATE users SET active = true WHERE active IS NULL")
    op.alter_column("users", "active", nullable=False)
    op.add_column("users", sa.Column("qc_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_users_qc_id_users", "users", "users", ["qc_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_users_qc_id_users", "users", type_="foreignkey")
    op.drop_column("users", "qc_id")
    op.drop_column("users", "active")
