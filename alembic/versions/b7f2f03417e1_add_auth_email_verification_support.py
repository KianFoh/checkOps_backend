"""add auth email verification support

Revision ID: b7f2f03417e1
Revises: 0cc1517098da
Create Date: 2026-05-18 15:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7f2f03417e1"
down_revision: Union[str, Sequence[str], None] = "0cc1517098da"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("users", "is_email_verified", server_default=None)

    op.create_table(
        "email_verification_otps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("otp_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_email_verification_otps_id"), "email_verification_otps", ["id"], unique=False)
    op.create_index(
        op.f("ix_email_verification_otps_user_id"),
        "email_verification_otps",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_email_verification_otps_user_id"), table_name="email_verification_otps")
    op.drop_index(op.f("ix_email_verification_otps_id"), table_name="email_verification_otps")
    op.drop_table("email_verification_otps")
    op.drop_column("users", "is_email_verified")
