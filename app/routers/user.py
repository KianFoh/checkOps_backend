from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from app.database import SessionLocal
from app.helpers.auth import create_email_verification_challenge
from app.helpers.auth import create_token
from app.helpers.auth import hash_password
from app.models.user import User
from app.models.user import UserRole
from app.schemas.auth import CreateUserRequest
from app.schemas.auth import CreateUserResponse
from app.schemas.auth import UserSummary

router = APIRouter(prefix="/users", tags=["Users"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("", response_model=CreateUserResponse)
def create_user(
    payload: CreateUserRequest,
    db: DBSession = Depends(get_db),
):
    existing_user = (
        db.query(User)
        .filter((User.email == payload.email) | (User.employee_id == payload.employee_id))
        .first()
    )
    if existing_user is not None:
        if existing_user.email == payload.email:
            detail = "Email already exists."
        else:
            detail = "Employee ID already exists."
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )

    try:
        role = UserRole(payload.role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role.",
        )

    user = User(
        email=payload.email,
        name=payload.name,
        employee_id=payload.employee_id,
        role=role,
        profile_pic=payload.profile_pic,
        password=hash_password(create_token()),
        is_email_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    create_email_verification_challenge(user=user, db=db)

    return CreateUserResponse(
        message="User created successfully. Activation email has been sent.",
        user=UserSummary(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role.value,
            is_email_verified=user.is_email_verified,
        ),
    )
