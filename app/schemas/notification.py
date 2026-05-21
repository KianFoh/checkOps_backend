from datetime import datetime

from pydantic import BaseModel


class NotificationSummary(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    type: str
    related_task_id: int | None = None
    related_task_entry_id: int | None = None
    read_at: datetime | None = None
    created_at: datetime


class ListNotificationsResponse(BaseModel):
    message: str
    notifications: list[NotificationSummary]


class NotificationResponse(BaseModel):
    message: str
    notification: NotificationSummary


class MessageResponse(BaseModel):
    message: str
