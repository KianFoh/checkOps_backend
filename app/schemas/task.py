from datetime import date

from pydantic import BaseModel


class TaskSummary(BaseModel):
    id: int
    name: str
    start_date: date
    end_date: date
    status: str
    operator_remark: str | None = None
    qc_remark: str | None = None
    operator_id: int
    location: str | None = None
    recurrence: str | None = None
    evidence: str | None = None


class CreateTaskRequest(BaseModel):
    name: str
    start_date: date
    end_date: date
    operator_id: int
    location: str | None = None
    recurrence: str | None = None


class UpdateTaskRequest(BaseModel):
    name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: str | None = None
    operator_remark: str | None = None
    qc_remark: str | None = None
    operator_id: int | None = None
    location: str | None = None
    recurrence: str | None = None
    evidence: str | None = None


class TaskResponse(BaseModel):
    message: str
    task: TaskSummary


class ListTasksResponse(BaseModel):
    message: str
    tasks: list[TaskSummary]


class MessageResponse(BaseModel):
    message: str
