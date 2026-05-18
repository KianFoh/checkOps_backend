from sqlalchemy import Column, Integer, String, Date, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base
import enum

class TaskStatus(enum.Enum):
    Pending = "Pending"
    InProgress = "InProgress"
    Completed = "Completed"
    Cancelled = "Cancelled"

class RecurrenceType(enum.Enum):
    Once = "Once"
    Daily = "Daily"
    Weekly = "Weekly"
    Monthly = "Monthly"
    Yearly = "Yearly"

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    status = Column(Enum(TaskStatus), default=TaskStatus.Pending, nullable=False)
    operator_remark = Column(Text)
    qc_remark = Column(Text)
    operator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    operator = relationship("User")
    location = Column(String)
    recurrence = Column(Enum(RecurrenceType), default=RecurrenceType.Once)
    evidence = Column(String)  # Path or URL to image/video
