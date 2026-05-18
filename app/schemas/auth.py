from datetime import datetime

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class UserSummary(BaseModel):
    id: int
    email: str
    name: str
    role: str
    is_email_verified: bool


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    access_token_expires_at: datetime
    refresh_token_expires_at: datetime
    user: UserSummary


class EmailRequest(BaseModel):
    email: str


class ValidateLinkRequest(BaseModel):
    email: str
    token: str
    type: str


class SetPasswordRequest(BaseModel):
    email: str
    otp: str
    token: str
    password: str = Field(min_length=8)


class ResetPasswordRequest(BaseModel):
    email: str
    otp: str
    token: str
    password: str = Field(min_length=8)


class MessageResponse(BaseModel):
    message: str


class LinkValidationResponse(BaseModel):
    message: str
    email: str
    flow_type: str
    expires_at: datetime
