from sqlalchemy import Boolean, Column, Integer, String, Enum
from app.database import Base
import enum

class UserRole(enum.Enum):
    Operator = "Operator"
    QC = "QC"
    Admin = "Admin"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    password = Column(String, nullable=False)
    is_email_verified = Column(Boolean, nullable=False, default=False)
    profile_pic = Column(String)
    employee_id = Column(String, unique=True, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
