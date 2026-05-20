from datetime import datetime

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserSummary(BaseModel):
    id: int
    email: str
    name: str
    employee_id: str | None = None
    role: str
    profile_pic: str | None = None
    active: bool
    is_email_verified: bool
    qc_id: int | None = None


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    access_token_expires_at: datetime
    refresh_token_expires_at: datetime
    user: UserSummary


class EmailRequest(BaseModel):
    email: str


class CreateUserRequest(BaseModel):
    email: str
    name: str
    employee_id: str
    role: str
    profile_pic: str | None = None
    qc_id: int | None = None


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


class CreateUserResponse(BaseModel):
    message: str
    user: UserSummary


class UpdateUserRequest(BaseModel):
    email: str | None = None
    name: str | None = None
    employee_id: str | None = None
    role: str | None = None
    profile_pic: str | None = None
    password: str | None = Field(default=None, min_length=8)
    qc_id: int | None = None
    active: bool | None = None
    is_email_verified: bool | None = None


class UpdateUserResponse(BaseModel):
    message: str
    user: UserSummary


class GetUserResponse(BaseModel):
    message: str
    user: UserSummary


class ListUsersResponse(BaseModel):
    message: str
    users: list[UserSummary]


class LinkValidationResponse(BaseModel):
    message: str
    email: str
    flow_type: str
    expires_at: datetime
