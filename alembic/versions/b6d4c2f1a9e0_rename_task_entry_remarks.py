"""rename task entry remarks

Revision ID: b6d4c2f1a9e0
Revises: 91c3e5a6b7d8
Create Date: 2026-05-21 21:25:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b6d4c2f1a9e0"
down_revision: Union[str, Sequence[str], None] = "91c3e5a6b7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "task_entries",
        "operator_remark",
        new_column_name="submission_remark",
    )
    op.alter_column(
        "task_entries",
        "qc_remark",
        new_column_name="review_remark",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "task_entries",
        "review_remark",
        new_column_name="qc_remark",
    )
    op.alter_column(
        "task_entries",
        "submission_remark",
        new_column_name="operator_remark",
    )
