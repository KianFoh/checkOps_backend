from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session as DBSession

from app.database import SessionLocal
from app.helpers.auth import create_email_verification_challenge
from app.helpers.auth import create_token
from app.helpers.auth import hash_password
from app.helpers.realtime import publish_user_event
from app.helpers.security import get_current_user
from app.helpers.security import require_roles
from app.models.user import User
from app.models.user import UserRole
from app.schemas.auth import CreateUserRequest
from app.schemas.auth import CreateUserResponse
from app.schemas.auth import GetUserResponse
from app.schemas.auth import ListUsersResponse
from app.schemas.auth import MessageResponse
from app.schemas.auth import UpdateUserRequest
from app.schemas.auth import UpdateUserResponse
from app.schemas.auth import UserSummary

router = APIRouter(prefix="/users", tags=["Users"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def to_user_summary(user: User) -> UserSummary:
    return UserSummary(
        id=user.id,
        email=user.email,
        name=user.name,
        employee_id=user.employee_id,
        role=user.role.value,
        profile_pic=user.profile_pic,
        active=user.active,
        is_email_verified=user.is_email_verified,
        qc_id=user.qc_id,
    )


def resolve_qc_assignment(qc_id: int | None, db: DBSession) -> User | None:
    if qc_id is None:
        return None

    qc_user = db.query(User).filter(User.id == qc_id).first()
    if qc_user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assigned QC user not found.",
        )

    if qc_user.role != UserRole.QC:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assigned QC user must have QC role.",
        )

    return qc_user


def get_active_admin_user_ids(db: DBSession) -> list[int]:
    return [
        user.id
        for user in db.query(User.id)
        .filter(User.role == UserRole.Admin, User.active == True)
        .all()
    ]


def publish_user_change(
    db: DBSession,
    event_name: str,
    target_user_id: int,
) -> None:
    publish_user_event(
        get_active_admin_user_ids(db) + [target_user_id],
        event_name,
        target_user_id,
    )


@router.get("", response_model=ListUsersResponse)
def get_users(
    search: str | None = Query(default=None),
    role: str | None = Query(default=None),
    roles: list[str] | None = Query(default=None),
    active: bool | None = Query(default=None),
    current_user: User = Depends(require_roles(UserRole.Admin)),
    db: DBSession = Depends(get_db),
):
    query = db.query(User)

    if search is not None:
        cleaned_search = search.strip()
        if cleaned_search:
            search_pattern = f"%{cleaned_search}%"
            query = query.filter(User.name.ilike(search_pattern))

    role_filters = roles or ([role] if role is not None else [])
    if role_filters:
        role_enums = []
        for role_value in role_filters:
            if not role_value:
                continue
            try:
                role_enums.append(UserRole(role_value))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid role filter.",
                )
        if role_enums:
            query = query.filter(User.role.in_(role_enums))

    elif role is not None:
        try:
            role_enum = UserRole(role)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid role filter.",
            )
        query = query.filter(User.role == role_enum)

    if active is not None:
        query = query.filter(User.active == active)

    users = query.order_by(User.id.asc()).all()

    return ListUsersResponse(
        message="Users retrieved successfully.",
        users=[to_user_summary(user) for user in users],
    )


@router.get("/{user_id}", response_model=GetUserResponse)
def get_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    target_user = db.query(User).filter(User.id == user_id).first()
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    is_admin = current_user.role == UserRole.Admin
    is_self = current_user.id == target_user.id
    if not is_admin and not is_self:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own profile.",
        )

    return GetUserResponse(
        message="User retrieved successfully.",
        user=to_user_summary(target_user),
    )


@router.post("", response_model=CreateUserResponse)
def create_user(
    payload: CreateUserRequest,
    current_user: User = Depends(require_roles(UserRole.Admin)),
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

    qc_user = resolve_qc_assignment(payload.qc_id, db)
    if role == UserRole.Operator and qc_user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Operator must be assigned to a QC user.",
        )
    if role != UserRole.Operator and payload.qc_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only Operator users can be assigned to a QC user.",
        )

    user = User(
        email=payload.email,
        name=payload.name,
        employee_id=payload.employee_id,
        role=role,
        profile_pic=payload.profile_pic,
        password=hash_password(create_token()),
        active=True,
        is_email_verified=False,
        qc_id=qc_user.id if qc_user else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    create_email_verification_challenge(user=user, db=db)
    publish_user_change(db, "user.created", user.id)

    return CreateUserResponse(
        message="User created successfully. Activation email has been sent.",
        user=to_user_summary(user),
    )


@router.patch("/{user_id}", response_model=UpdateUserResponse)
def update_user(
    user_id: int,
    payload: UpdateUserRequest,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    target_user = db.query(User).filter(User.id == user_id).first()
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update.",
        )

    is_admin = current_user.role == UserRole.Admin
    is_self = current_user.id == target_user.id

    if not is_admin and not is_self:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own profile.",
        )

    allowed_self_fields = {"profile_pic"}
    if not is_admin:
        disallowed_fields = sorted(set(update_data) - allowed_self_fields)
        if disallowed_fields:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "You can only update your own profile picture. "
                    f"Disallowed fields: {', '.join(disallowed_fields)}."
                ),
            )

    if "email" in update_data:
        existing_email_user = (
            db.query(User)
            .filter(User.email == update_data["email"], User.id != target_user.id)
            .first()
        )
        if existing_email_user is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists.",
            )
        target_user.email = update_data["email"]

    if "employee_id" in update_data:
        existing_employee_user = (
            db.query(User)
            .filter(User.employee_id == update_data["employee_id"], User.id != target_user.id)
            .first()
        )
        if existing_employee_user is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Employee ID already exists.",
            )
        target_user.employee_id = update_data["employee_id"]

    if "name" in update_data:
        target_user.name = update_data["name"]

    if "profile_pic" in update_data:
        target_user.profile_pic = update_data["profile_pic"]

    if "password" in update_data:
        target_user.password = hash_password(update_data["password"])

    if "role" in update_data:
        try:
            target_user.role = UserRole(update_data["role"])
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid role.",
            )

    if "active" in update_data:
        target_user.active = update_data["active"]

    if "is_email_verified" in update_data:
        target_user.is_email_verified = update_data["is_email_verified"]

    if "qc_id" in update_data:
        qc_user = resolve_qc_assignment(update_data["qc_id"], db)
        target_user.qc_id = qc_user.id if qc_user else None

    if target_user.role == UserRole.Operator and target_user.qc_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Operator must be assigned to a QC user.",
        )

    if target_user.role != UserRole.Operator and target_user.qc_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only Operator users can be assigned to a QC user.",
        )

    db.commit()
    db.refresh(target_user)
    publish_user_change(db, "user.updated", target_user.id)

    return UpdateUserResponse(
        message="User updated successfully.",
        user=to_user_summary(target_user),
    )

