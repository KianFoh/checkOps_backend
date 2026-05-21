"""redesign tasks and entries

Revision ID: 8b1d4f6a7c20
Revises: 3f6b8c9d2a10
Create Date: 2026-05-21 20:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "8b1d4f6a7c20"
down_revision: Union[str, Sequence[str], None] = "3f6b8c9d2a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE TYPE taskrecurrencetype AS ENUM ('Once', 'Recurring')")
    op.execute("CREATE TYPE intervalunit AS ENUM ('Day', 'Week', 'Month', 'Year')")

    op.alter_column("tasks", "operator_id", new_column_name="user_id")
    op.add_column(
        "tasks",
        sa.Column(
            "recurrence_type",
            postgresql.ENUM(
                "Once",
                "Recurring",
                name="taskrecurrencetype",
                create_type=False,
            ),
            nullable=True,
        ),
    )
    op.add_column("tasks", sa.Column("recurrence_interval", sa.Integer(), nullable=True))
    op.add_column(
        "tasks",
        sa.Column(
            "recurrence_unit",
            postgresql.ENUM(
                "Day",
                "Week",
                "Month",
                "Year",
                name="intervalunit",
                create_type=False,
            ),
            nullable=True,
        ),
    )
    op.add_column("tasks", sa.Column("recurrence_start_at", sa.DateTime(), nullable=True))
    op.add_column("tasks", sa.Column("due_interval", sa.Integer(), nullable=True))
    op.add_column(
        "tasks",
        sa.Column(
            "due_interval_unit",
            postgresql.ENUM(
                "Day",
                "Week",
                "Month",
                "Year",
                name="intervalunit",
                create_type=False,
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "tasks",
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true()),
    )

    op.execute(
        """
        UPDATE tasks
        SET
            recurrence_type = (
                CASE
                    WHEN recurrence IS NULL OR recurrence::text = 'Once' THEN 'Once'
                    ELSE 'Recurring'
                END
            )::taskrecurrencetype,
            recurrence_interval = 1,
            recurrence_unit = (
                CASE recurrence::text
                    WHEN 'Daily' THEN 'Day'
                    WHEN 'Weekly' THEN 'Week'
                    WHEN 'Monthly' THEN 'Month'
                    WHEN 'Yearly' THEN 'Year'
                    ELSE NULL
                END
            )::intervalunit,
            recurrence_start_at = start_date::timestamp,
            due_interval = GREATEST(end_date - start_date, 0),
            due_interval_unit = 'Day'::intervalunit,
            is_active = TRUE
        """
    )

    op.create_table(
        "task_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column("due_at", sa.DateTime(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "Pending",
                "Completed",
                "Failed",
                "Approved",
                "Rejected",
                "Expired",
                name="taskstatus",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("operator_remark", sa.Text(), nullable=True),
        sa.Column("qc_remark", sa.Text(), nullable=True),
        sa.Column("evidence", sa.String(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_task_entries_id"), "task_entries", ["id"], unique=False)

    op.execute(
        """
        INSERT INTO task_entries (
            task_id,
            user_id,
            scheduled_at,
            due_at,
            status,
            operator_remark,
            qc_remark,
            evidence,
            completed_at
        )
        SELECT
            id,
            user_id,
            start_date::timestamp,
            end_date::timestamp,
            status,
            operator_remark,
            qc_remark,
            evidence,
            CASE
                WHEN status::text = 'Completed' THEN end_date::timestamp
                ELSE NULL
            END
        FROM tasks
        """
    )

    op.alter_column("tasks", "recurrence_type", nullable=False)
    op.alter_column("tasks", "recurrence_interval", nullable=False)
    op.alter_column("tasks", "recurrence_start_at", nullable=False)
    op.alter_column("tasks", "due_interval", nullable=False)
    op.alter_column("tasks", "due_interval_unit", nullable=False)
    op.alter_column("tasks", "is_active", nullable=False, server_default=None)

    op.drop_column("tasks", "status")
    op.drop_column("tasks", "operator_remark")
    op.drop_column("tasks", "qc_remark")
    op.drop_column("tasks", "evidence")
    op.drop_column("tasks", "start_date")
    op.drop_column("tasks", "end_date")
    op.drop_column("tasks", "recurrence")
    op.execute("DROP TYPE recurrencetype")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        "CREATE TYPE recurrencetype AS ENUM "
        "('Once', 'Daily', 'Weekly', 'Monthly', 'Yearly')"
    )

    op.add_column("tasks", sa.Column("start_date", sa.Date(), nullable=True))
    op.add_column("tasks", sa.Column("end_date", sa.Date(), nullable=True))
    op.add_column(
        "tasks",
        sa.Column(
            "status",
            postgresql.ENUM(
                "Pending",
                "Completed",
                "Failed",
                "Approved",
                "Rejected",
                "Expired",
                name="taskstatus",
                create_type=False,
            ),
            nullable=True,
        ),
    )
    op.add_column("tasks", sa.Column("operator_remark", sa.Text(), nullable=True))
    op.add_column("tasks", sa.Column("qc_remark", sa.Text(), nullable=True))
    op.add_column("tasks", sa.Column("evidence", sa.String(), nullable=True))
    op.add_column(
        "tasks",
        sa.Column(
            "recurrence",
            postgresql.ENUM(
                "Once",
                "Daily",
                "Weekly",
                "Monthly",
                "Yearly",
                name="recurrencetype",
                create_type=False,
            ),
            nullable=True,
        ),
    )

    op.execute(
        """
        WITH first_entries AS (
            SELECT DISTINCT ON (task_id)
                task_id,
                scheduled_at,
                due_at,
                status,
                operator_remark,
                qc_remark,
                evidence
            FROM task_entries
            ORDER BY task_id, scheduled_at, id
        )
        UPDATE tasks
        SET
            start_date = COALESCE(first_entries.scheduled_at::date, recurrence_start_at::date),
            end_date = COALESCE(first_entries.due_at::date, recurrence_start_at::date),
            status = COALESCE(first_entries.status, 'Pending'::taskstatus),
            operator_remark = first_entries.operator_remark,
            qc_remark = first_entries.qc_remark,
            evidence = first_entries.evidence,
            recurrence = (
                CASE
                    WHEN recurrence_type::text = 'Once' THEN 'Once'
                    WHEN recurrence_unit::text = 'Day' THEN 'Daily'
                    WHEN recurrence_unit::text = 'Week' THEN 'Weekly'
                    WHEN recurrence_unit::text = 'Month' THEN 'Monthly'
                    WHEN recurrence_unit::text = 'Year' THEN 'Yearly'
                    ELSE 'Once'
                END
            )::recurrencetype
        FROM first_entries
        WHERE tasks.id = first_entries.task_id
        """
    )

    op.execute(
        """
        UPDATE tasks
        SET
            start_date = COALESCE(start_date, recurrence_start_at::date),
            end_date = COALESCE(end_date, recurrence_start_at::date),
            status = COALESCE(status, 'Pending'::taskstatus),
            recurrence = COALESCE(recurrence, 'Once'::recurrencetype)
        """
    )

    op.alter_column("tasks", "start_date", nullable=False)
    op.alter_column("tasks", "end_date", nullable=False)
    op.alter_column("tasks", "status", nullable=False)

    op.drop_index(op.f("ix_task_entries_id"), table_name="task_entries")
    op.drop_table("task_entries")

    op.drop_column("tasks", "is_active")
    op.drop_column("tasks", "due_interval_unit")
    op.drop_column("tasks", "due_interval")
    op.drop_column("tasks", "recurrence_start_at")
    op.drop_column("tasks", "recurrence_unit")
    op.drop_column("tasks", "recurrence_interval")
    op.drop_column("tasks", "recurrence_type")
    op.alter_column("tasks", "user_id", new_column_name="operator_id")

    op.execute("DROP TYPE intervalunit")
    op.execute("DROP TYPE taskrecurrencetype")
