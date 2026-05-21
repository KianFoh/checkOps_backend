"""add task entry submission review metadata

Revision ID: 91c3e5a6b7d8
Revises: 8b1d4f6a7c20
Create Date: 2026-05-21 21:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "91c3e5a6b7d8"
down_revision: Union[str, Sequence[str], None] = "8b1d4f6a7c20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("task_entries", "completed_at", new_column_name="submitted_at")
    op.add_column("task_entries", sa.Column("submitted_by_user_id", sa.Integer(), nullable=True))
    op.add_column("task_entries", sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True))
    op.add_column("task_entries", sa.Column("reviewed_at", sa.DateTime(), nullable=True))

    op.execute(
        """
        UPDATE task_entries
        SET submitted_by_user_id = user_id
        WHERE submitted_at IS NOT NULL
        """
    )

    op.create_foreign_key(
        "fk_task_entries_submitted_by_user_id_users",
        "task_entries",
        "users",
        ["submitted_by_user_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_task_entries_reviewed_by_user_id_users",
        "task_entries",
        "users",
        ["reviewed_by_user_id"],
        ["id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_task_entries_reviewed_by_user_id_users",
        "task_entries",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_task_entries_submitted_by_user_id_users",
        "task_entries",
        type_="foreignkey",
    )
    op.drop_column("task_entries", "reviewed_at")
    op.drop_column("task_entries", "reviewed_by_user_id")
    op.drop_column("task_entries", "submitted_by_user_id")
    op.alter_column("task_entries", "submitted_at", new_column_name="completed_at")
