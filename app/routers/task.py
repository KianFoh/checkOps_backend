from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session as DBSession

from app.database import SessionLocal
from app.helpers.security import get_current_user
from app.helpers.security import require_roles
from app.models.task import RecurrenceType
from app.models.task import Task
from app.models.task import TaskStatus
from app.models.user import User
from app.models.user import UserRole
from app.schemas.task import CreateTaskRequest
from app.schemas.task import ListTasksResponse
from app.schemas.task import MessageResponse
from app.schemas.task import TaskResponse
from app.schemas.task import TaskSummary
from app.schemas.task import UpdateTaskRequest

router = APIRouter(prefix="/tasks", tags=["Tasks"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def to_task_summary(task: Task) -> TaskSummary:
    return TaskSummary(
        id=task.id,
        name=task.name,
        start_date=task.start_date,
        end_date=task.end_date,
        status=task.status.value,
        operator_remark=task.operator_remark,
        qc_remark=task.qc_remark,
        operator_id=task.operator_id,
        location=task.location,
        recurrence=task.recurrence.value if task.recurrence else None,
        evidence=task.evidence,
    )


def parse_task_status(value: str) -> TaskStatus:
    try:
        return TaskStatus(value)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid task status.",
        )


def parse_recurrence(value: str | None) -> RecurrenceType | None:
    if value is None:
        return None

    try:
        return RecurrenceType(value)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid recurrence.",
        )


def validate_date_range(start_date: date, end_date: date) -> None:
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date cannot be before start date.",
        )


def get_operator(operator_id: int, db: DBSession) -> User:
    operator = db.query(User).filter(User.id == operator_id).first()
    if operator is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Operator not found.",
        )

    if operator.role != UserRole.Operator:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task can only be assigned to an Operator user.",
        )

    return operator


def can_access_task(task: Task, current_user: User) -> bool:
    if current_user.role == UserRole.Admin:
        return True
    if current_user.role == UserRole.Operator:
        return task.operator_id == current_user.id
    if current_user.role == UserRole.QC:
        return task.operator is not None and task.operator.qc_id == current_user.id
    return False


@router.get("", response_model=ListTasksResponse)
def get_tasks(
    search: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    operator_id: int | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    query = db.query(Task).join(User, Task.operator_id == User.id)

    if current_user.role == UserRole.Operator:
        query = query.filter(Task.operator_id == current_user.id)
    elif current_user.role == UserRole.QC:
        query = query.filter(User.qc_id == current_user.id)

    if search is not None:
        cleaned_search = search.strip()
        if cleaned_search:
            search_pattern = f"%{cleaned_search}%"
            query = query.filter(
                (Task.name.ilike(search_pattern))
                | (Task.location.ilike(search_pattern))
            )

    if status_filter is not None:
        query = query.filter(Task.status == parse_task_status(status_filter))

    if operator_id is not None:
        query = query.filter(Task.operator_id == operator_id)

    if start_date is not None:
        query = query.filter(Task.start_date >= start_date)

    if end_date is not None:
        query = query.filter(Task.end_date <= end_date)

    tasks = query.order_by(Task.start_date.asc(), Task.id.asc()).all()

    return ListTasksResponse(
        message="Tasks retrieved successfully.",
        tasks=[to_task_summary(task) for task in tasks],
    )


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found.",
        )

    if not can_access_task(task, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this task.",
        )

    return TaskResponse(
        message="Task retrieved successfully.",
        task=to_task_summary(task),
    )


@router.post("", response_model=TaskResponse)
def create_task(
    payload: CreateTaskRequest,
    current_user: User = Depends(require_roles(UserRole.Admin)),
    db: DBSession = Depends(get_db),
):
    validate_date_range(payload.start_date, payload.end_date)
    get_operator(payload.operator_id, db)

    task = Task(
        name=payload.name,
        start_date=payload.start_date,
        end_date=payload.end_date,
        operator_id=payload.operator_id,
        location=payload.location,
        recurrence=parse_recurrence(payload.recurrence) or RecurrenceType.Once,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    return TaskResponse(
        message="Task created successfully.",
        task=to_task_summary(task),
    )


@router.patch("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int,
    payload: UpdateTaskRequest,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found.",
        )

    if not can_access_task(task, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this task.",
        )

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update.",
        )

    if current_user.role == UserRole.Operator:
        allowed_fields = {"status", "operator_remark", "evidence"}
    elif current_user.role == UserRole.QC:
        allowed_fields = {"status", "qc_remark"}
    else:
        allowed_fields = set(update_data)

    disallowed_fields = sorted(set(update_data) - allowed_fields)
    if disallowed_fields:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Disallowed fields: {', '.join(disallowed_fields)}.",
        )

    if "name" in update_data:
        task.name = update_data["name"]

    if "start_date" in update_data:
        task.start_date = update_data["start_date"]

    if "end_date" in update_data:
        task.end_date = update_data["end_date"]

    validate_date_range(task.start_date, task.end_date)

    if "status" in update_data:
        task.status = parse_task_status(update_data["status"])

    if "operator_remark" in update_data:
        task.operator_remark = update_data["operator_remark"]

    if "qc_remark" in update_data:
        task.qc_remark = update_data["qc_remark"]

    if "operator_id" in update_data:
        get_operator(update_data["operator_id"], db)
        task.operator_id = update_data["operator_id"]

    if "location" in update_data:
        task.location = update_data["location"]

    if "recurrence" in update_data:
        task.recurrence = parse_recurrence(update_data["recurrence"])

    if "evidence" in update_data:
        task.evidence = update_data["evidence"]

    db.commit()
    db.refresh(task)

    return TaskResponse(
        message="Task updated successfully.",
        task=to_task_summary(task),
    )


@router.delete("/{task_id}", response_model=MessageResponse)
def delete_task(
    task_id: int,
    current_user: User = Depends(require_roles(UserRole.Admin)),
    db: DBSession = Depends(get_db),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found.",
        )

    db.delete(task)
    db.commit()

    return MessageResponse(message="Task deleted successfully.")
