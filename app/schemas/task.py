from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

TaskStatusValue = Literal[
    "Pending",
    "Submitted",
    "Failed",
    "Approved",
    "Rejected",
    "Expired",
]
RecurrenceTypeValue = Literal["Once", "Recurring"]
IntervalUnitValue = Literal["Day", "Week", "Month", "Year"]


class TaskEntrySummary(BaseModel):
    id: int
    task_id: int
    user_id: int
    start_at: datetime
    due_at: datetime
    is_available_for_submission: bool
    status: TaskStatusValue
    submission_remark: str | None = None
    review_remark: str | None = None
    evidence: str | None = None
    submitted_by_user_id: int | None = None
    reviewed_by_user_id: int | None = None
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None


class TaskEntryLiteSummary(BaseModel):
    id: int
    task_id: int
    user_id: int
    start_at: datetime
    due_at: datetime
    status: TaskStatusValue


class TaskSummary(BaseModel):
    id: int
    name: str
    description: str | None = None
    user_id: int
    location: str | None = None
    recurrence_type: RecurrenceTypeValue
    recurrence_interval: int
    recurrence_unit: IntervalUnitValue | None = None
    recurrence_start_at: datetime
    due_interval: int
    due_interval_unit: IntervalUnitValue
    is_active: bool


class CreateTaskRequest(BaseModel):
    name: str
    description: str | None = None
    user_id: int
    location: str | None = None
    recurrence_type: RecurrenceTypeValue = "Once"
    recurrence_interval: int = Field(default=1, ge=1)
    recurrence_unit: IntervalUnitValue | None = None
    recurrence_start_at: datetime
    due_interval: int = Field(default=1, ge=0)
    due_interval_unit: IntervalUnitValue = "Day"
    is_active: bool = True


class UpdateTaskRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    user_id: int | None = None
    location: str | None = None
    recurrence_type: RecurrenceTypeValue | None = None
    recurrence_interval: int | None = Field(default=None, ge=1)
    recurrence_unit: IntervalUnitValue | None = None
    recurrence_start_at: datetime | None = None
    due_interval: int | None = Field(default=None, ge=0)
    due_interval_unit: IntervalUnitValue | None = None
    is_active: bool | None = None


class CreateTaskEntryRequest(BaseModel):
    user_id: int | None = None
    start_at: datetime
    due_at: datetime | None = None


class UpdateTaskEntryRequest(BaseModel):
    user_id: int | None = None
    start_at: datetime | None = None
    due_at: datetime | None = None
    status: TaskStatusValue | None = None
    submission_remark: str | None = None
    review_remark: str | None = None
    evidence: str | None = None


class GenerateTaskEntriesRequest(BaseModel):
    occurrences: int = Field(default=1, ge=1, le=366)


class TaskResponse(BaseModel):
    message: str
    task: TaskSummary


class ListTasksResponse(BaseModel):
    message: str
    tasks: list[TaskSummary]


class TaskEntryResponse(BaseModel):
    message: str
    entry: TaskEntrySummary


class ListTaskEntriesResponse(BaseModel):
    message: str
    entries: list[TaskEntrySummary]


class ListTaskEntryLiteResponse(BaseModel):
    message: str
    entries: list[TaskEntryLiteSummary]


class GenerateTaskEntriesResponse(BaseModel):
    message: str
    entries: list[TaskEntrySummary]


class MessageResponse(BaseModel):
    message: str
