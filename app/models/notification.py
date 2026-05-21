from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    user = relationship("User")
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String, nullable=False, index=True)
    related_task_id = Column(Integer, ForeignKey("tasks.id"))
    related_task = relationship("Task")
    related_task_entry_id = Column(Integer, ForeignKey("task_entries.id"))
    related_task_entry = relationship("TaskEntry")
    read_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
