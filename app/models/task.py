import enum

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class TaskStatus(enum.Enum):
    Pending = "Pending"
    Completed = "Completed"
    Failed = "Failed"
    Approved = "Approved"
    Rejected = "Rejected"
    Expired = "Expired"


class RecurrenceType(enum.Enum):
    Once = "Once"
    Recurring = "Recurring"


class IntervalUnit(enum.Enum):
    Day = "Day"
    Week = "Week"
    Month = "Month"
    Year = "Year"


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", foreign_keys=[user_id])
    location = Column(String)
    recurrence_type = Column(Enum(RecurrenceType, name="taskrecurrencetype"), nullable=False)
    recurrence_interval = Column(Integer, nullable=False, default=1)
    recurrence_unit = Column(Enum(IntervalUnit, name="intervalunit"))
    recurrence_start_at = Column(DateTime, nullable=False)
    due_interval = Column(Integer, nullable=False, default=1)
    due_interval_unit = Column(Enum(IntervalUnit, name="intervalunit"), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)

    entries = relationship(
        "TaskEntry",
        back_populates="task",
        cascade="all, delete-orphan",
    )


class TaskEntry(Base):
    __tablename__ = "task_entries"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    task = relationship("Task", back_populates="entries")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", foreign_keys=[user_id])
    start_at = Column(DateTime, nullable=False)
    due_at = Column(DateTime, nullable=False)
    status = Column(Enum(TaskStatus), default=TaskStatus.Pending, nullable=False)
    submission_remark = Column(Text)
    review_remark = Column(Text)
    evidence = Column(String)
    submitted_by_user_id = Column(Integer, ForeignKey("users.id"))
    submitted_by_user = relationship("User", foreign_keys=[submitted_by_user_id])
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id"))
    reviewed_by_user = relationship("User", foreign_keys=[reviewed_by_user_id])
    submitted_at = Column(DateTime)
    reviewed_at = Column(DateTime)
