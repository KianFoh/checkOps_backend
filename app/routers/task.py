import calendar
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session as DBSession

from app.database import SessionLocal
from app.helpers.security import get_current_user
from app.helpers.security import require_roles
from app.models.task import IntervalUnit
from app.models.task import RecurrenceType
from app.models.task import Task
from app.models.task import TaskEntry
from app.models.task import TaskStatus
from app.models.user import User
from app.models.user import UserRole
from app.schemas.task import CreateTaskEntryRequest
from app.schemas.task import CreateTaskRequest
from app.schemas.task import GenerateTaskEntriesRequest
from app.schemas.task import GenerateTaskEntriesResponse
from app.schemas.task import ListTaskEntriesResponse
from app.schemas.task import ListTasksResponse
from app.schemas.task import MessageResponse
from app.schemas.task import TaskEntryResponse
from app.schemas.task import TaskEntrySummary
from app.schemas.task import TaskResponse
from app.schemas.task import TaskSummary
from app.schemas.task import UpdateTaskEntryRequest
from app.schemas.task import UpdateTaskRequest

router = APIRouter(prefix="/tasks", tags=["Tasks"])

FINAL_TASK_STATUSES = {
    TaskStatus.Failed,
    TaskStatus.Approved,
    TaskStatus.Rejected,
    TaskStatus.Expired,
}


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
        description=task.description,
        user_id=task.user_id,
        location=task.location,
        recurrence_type=task.recurrence_type.value,
        recurrence_interval=task.recurrence_interval,
        recurrence_unit=task.recurrence_unit.value if task.recurrence_unit else None,
        recurrence_start_at=task.recurrence_start_at,
        due_interval=task.due_interval,
        due_interval_unit=task.due_interval_unit.value,
        is_active=task.is_active,
    )


def to_task_entry_summary(entry: TaskEntry) -> TaskEntrySummary:
    return TaskEntrySummary(
        id=entry.id,
        task_id=entry.task_id,
        user_id=entry.user_id,
        start_at=entry.start_at,
        due_at=entry.due_at,
        is_available_for_submission=is_available_for_submission(entry),
        status=entry.status.value,
        submission_remark=entry.submission_remark,
        review_remark=entry.review_remark,
        evidence=entry.evidence,
        submitted_by_user_id=entry.submitted_by_user_id,
        reviewed_by_user_id=entry.reviewed_by_user_id,
        submitted_at=entry.submitted_at,
        reviewed_at=entry.reviewed_at,
    )


def parse_task_status(value: str) -> TaskStatus:
    try:
        return TaskStatus(value)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid task status.",
        )


def parse_recurrence_type(value: str) -> RecurrenceType:
    try:
        return RecurrenceType(value)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid recurrence type.",
        )


def parse_interval_unit(value: str | None) -> IntervalUnit | None:
    if value is None:
        return None

    try:
        return IntervalUnit(value)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid interval unit.",
        )


def get_user(user_id: int, db: DBSession) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found.",
        )
    return user


def validate_task_recurrence(
    recurrence_type: RecurrenceType,
    recurrence_interval: int,
    recurrence_unit: IntervalUnit | None,
) -> None:
    if recurrence_interval < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Recurrence interval must be at least 1.",
        )

    if recurrence_type == RecurrenceType.Recurring and recurrence_unit is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Recurring tasks require a recurrence unit.",
        )

    if recurrence_type == RecurrenceType.Once and recurrence_unit is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Once tasks cannot have a recurrence unit.",
        )


def validate_due_interval(due_interval: int) -> None:
    if due_interval < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Due interval cannot be negative.",
        )


def add_interval(value: datetime, interval: int, unit: IntervalUnit) -> datetime:
    if unit == IntervalUnit.Day:
        return value + timedelta(days=interval)
    if unit == IntervalUnit.Week:
        return value + timedelta(weeks=interval)

    month_index = value.month - 1
    year = value.year
    month = value.month
    if unit == IntervalUnit.Month:
        month_index += interval
        year += month_index // 12
        month = month_index % 12 + 1
    elif unit == IntervalUnit.Year:
        year += interval

    last_day = calendar.monthrange(year, month)[1]
    return value.replace(year=year, month=month, day=min(value.day, last_day))


def calculate_due_at(task: Task, start_at: datetime) -> datetime:
    return add_interval(start_at, task.due_interval, task.due_interval_unit)


def make_entry(
    task: Task,
    start_at: datetime,
    user_id: int | None = None,
    due_at: datetime | None = None,
    status_value: str = TaskStatus.Pending.value,
) -> TaskEntry:
    return TaskEntry(
        task_id=task.id,
        user_id=user_id or task.user_id,
        start_at=start_at,
        due_at=due_at or calculate_due_at(task, start_at),
        status=parse_task_status(status_value),
    )


def is_available_for_submission(entry: TaskEntry, now: datetime | None = None) -> bool:
    expire_entry_if_overdue(entry, now)
    current_time = now or datetime.now()
    return (
        entry.status == TaskStatus.Pending
        and entry.start_at <= current_time <= entry.due_at
    )


def validate_submission_window(entry: TaskEntry) -> None:
    expire_entry_if_overdue(entry)
    if is_available_for_submission(entry):
        return

    if entry.status != TaskStatus.Pending:
        detail = "Only pending task entries can be submitted."
    elif datetime.now() < entry.start_at:
        detail = "Task entry is not available for submission yet."
    else:
        detail = "Task entry is past due and cannot be submitted."

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=detail,
    )


def expire_entry_if_overdue(entry: TaskEntry, now: datetime | None = None) -> bool:
    current_time = now or datetime.now()
    if entry.status in (TaskStatus.Pending, TaskStatus.Completed) and entry.due_at < current_time:
        entry.status = TaskStatus.Expired
        return True
    return False


def expire_overdue_entries(db: DBSession) -> None:
    now = datetime.now()
    updated = (
        db.query(TaskEntry)
        .filter(
            TaskEntry.status.in_([TaskStatus.Pending, TaskStatus.Completed]),
            TaskEntry.due_at < now,
        )
        .update({TaskEntry.status: TaskStatus.Expired}, synchronize_session=False)
    )
    if updated:
        db.commit()


def expire_entry_for_request(entry: TaskEntry, db: DBSession) -> None:
    if expire_entry_if_overdue(entry):
        db.commit()
        db.refresh(entry)


def is_allowed_qc_for_user(user: User | None, current_user: User) -> bool:
    if user is None or current_user.role != UserRole.QC:
        return False
    return user.id == current_user.id or user.qc_id == current_user.id


def can_edit_pending_entry(entry: TaskEntry, current_user: User) -> bool:
    return current_user.role == UserRole.Admin or is_allowed_qc_for_user(entry.user, current_user)


def can_review_entry(entry: TaskEntry, current_user: User) -> bool:
    return current_user.role == UserRole.Admin or is_allowed_qc_for_user(entry.user, current_user)


def require_pending_entry(entry: TaskEntry) -> None:
    if entry.status == TaskStatus.Pending:
        return

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Only pending task entries can be edited before submission.",
    )


def require_not_final_entry(entry: TaskEntry) -> None:
    if entry.status not in FINAL_TASK_STATUSES:
        return

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Final task entries cannot be updated.",
    )


def require_submission_remark(update_data: dict) -> str:
    remark = update_data.get("submission_remark")
    if not isinstance(remark, str) or not remark.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Submission remark is required when failing a task entry.",
        )
    return remark


def require_review_remark(update_data: dict) -> str:
    remark = update_data.get("review_remark")
    if not isinstance(remark, str) or not remark.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Review remark is required when rejecting a task entry.",
        )
    return remark


def validate_entry_times(start_at: datetime, due_at: datetime) -> None:
    if due_at < start_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Due date cannot be before start date.",
        )


def validate_task_entry_update(
    entry: TaskEntry,
    update_data: dict,
    current_user: User,
) -> TaskStatus | None:
    next_status = parse_task_status(update_data["status"]) if "status" in update_data else None
    schedule_fields = {"user_id", "start_at", "due_at"}
    submission_fields = {"status", "submission_remark", "evidence"}
    review_fields = {"status", "review_remark"}

    require_not_final_entry(entry)

    if schedule_fields & update_data.keys():
        require_pending_entry(entry)
        if not can_edit_pending_entry(entry, current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to edit this pending task entry.",
            )

        disallowed = sorted(set(update_data) - schedule_fields)
        if disallowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Schedule changes cannot be combined with: {', '.join(disallowed)}.",
            )
        return next_status

    if entry.status == TaskStatus.Pending:
        if next_status not in (TaskStatus.Completed, TaskStatus.Failed):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pending task entries can only be submitted as Completed or Failed.",
            )

        if entry.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the assigned user can submit this task entry.",
            )

        disallowed = sorted(set(update_data) - submission_fields)
        if disallowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Submission cannot include: {', '.join(disallowed)}.",
            )

        validate_submission_window(entry)

        if next_status == TaskStatus.Failed:
            require_submission_remark(update_data)

        return next_status

    if entry.status == TaskStatus.Completed:
        if next_status not in (TaskStatus.Approved, TaskStatus.Rejected):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Completed task entries can only be reviewed as Approved or Rejected.",
            )

        if not can_review_entry(entry, current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to review this task entry.",
            )

        disallowed = sorted(set(update_data) - review_fields)
        if disallowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Review cannot include: {', '.join(disallowed)}.",
            )

        if datetime.now() > entry.due_at:
            entry.status = TaskStatus.Expired
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Task entry is past due and has expired.",
            )

        if next_status == TaskStatus.Rejected:
            require_review_remark(update_data)

        return next_status

    return next_status


def next_start_at(task: Task, last_start_at: datetime | None) -> datetime | None:
    if task.recurrence_type == RecurrenceType.Once:
        return task.recurrence_start_at if last_start_at is None else None

    if task.recurrence_unit is None:
        return None

    if last_start_at is None:
        return task.recurrence_start_at

    return add_interval(
        last_start_at,
        task.recurrence_interval,
        task.recurrence_unit,
    )


def can_access_user(user: User, current_user: User) -> bool:
    if current_user.role == UserRole.Admin:
        return True
    if user.id == current_user.id:
        return True
    if current_user.role == UserRole.QC:
        return user.qc_id == current_user.id
    return False


def can_access_task(task: Task, current_user: User) -> bool:
    return task.user is not None and can_access_user(task.user, current_user)


def can_access_entry(entry: TaskEntry, current_user: User) -> bool:
    if current_user.role == UserRole.Admin:
        return True
    if entry.user_id == current_user.id:
        return True
    if current_user.role == UserRole.QC:
        return entry.user is not None and entry.user.qc_id == current_user.id
    return can_access_task(entry.task, current_user)


@router.get("", response_model=ListTasksResponse)
def get_tasks(
    search: str | None = Query(default=None),
    user_id: int | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    recurrence_type: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    query = db.query(Task).join(User, Task.user_id == User.id)

    if current_user.role != UserRole.Admin:
        if current_user.role == UserRole.QC:
            query = query.filter((Task.user_id == current_user.id) | (User.qc_id == current_user.id))
        else:
            query = query.filter(Task.user_id == current_user.id)

    if search is not None:
        cleaned_search = search.strip()
        if cleaned_search:
            search_pattern = f"%{cleaned_search}%"
            query = query.filter(
                or_(
                    Task.name.ilike(search_pattern),
                    Task.description.ilike(search_pattern),
                    Task.location.ilike(search_pattern),
                )
            )

    if user_id is not None:
        query = query.filter(Task.user_id == user_id)

    if is_active is not None:
        query = query.filter(Task.is_active == is_active)

    if recurrence_type is not None:
        query = query.filter(Task.recurrence_type == parse_recurrence_type(recurrence_type))

    tasks = query.order_by(Task.recurrence_start_at.asc(), Task.id.asc()).all()

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
    get_user(payload.user_id, db)
    recurrence_type = parse_recurrence_type(payload.recurrence_type)
    recurrence_unit = parse_interval_unit(payload.recurrence_unit)
    due_interval_unit = parse_interval_unit(payload.due_interval_unit)
    validate_task_recurrence(
        recurrence_type,
        payload.recurrence_interval,
        recurrence_unit,
    )
    validate_due_interval(payload.due_interval)

    task = Task(
        name=payload.name,
        description=payload.description,
        user_id=payload.user_id,
        location=payload.location,
        recurrence_type=recurrence_type,
        recurrence_interval=payload.recurrence_interval,
        recurrence_unit=recurrence_unit,
        recurrence_start_at=payload.recurrence_start_at,
        due_interval=payload.due_interval,
        due_interval_unit=due_interval_unit,
        is_active=payload.is_active,
    )
    db.add(task)
    db.flush()

    db.add(make_entry(task, start_at=task.recurrence_start_at))
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
    current_user: User = Depends(require_roles(UserRole.Admin)),
    db: DBSession = Depends(get_db),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found.",
        )

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update.",
        )

    if "user_id" in update_data:
        get_user(update_data["user_id"], db)
        task.user_id = update_data["user_id"]

    for field in ("name", "description", "location", "recurrence_start_at", "is_active"):
        if field in update_data:
            setattr(task, field, update_data[field])

    if "recurrence_type" in update_data:
        task.recurrence_type = parse_recurrence_type(update_data["recurrence_type"])

    if "recurrence_interval" in update_data:
        task.recurrence_interval = update_data["recurrence_interval"]

    if "recurrence_unit" in update_data:
        task.recurrence_unit = parse_interval_unit(update_data["recurrence_unit"])

    if "due_interval" in update_data:
        task.due_interval = update_data["due_interval"]

    if "due_interval_unit" in update_data:
        task.due_interval_unit = parse_interval_unit(update_data["due_interval_unit"])

    validate_task_recurrence(
        task.recurrence_type,
        task.recurrence_interval,
        task.recurrence_unit,
    )
    validate_due_interval(task.due_interval)

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


@router.get("/{task_id}/entries", response_model=ListTaskEntriesResponse)
def get_task_entries(
    task_id: int,
    status_filter: str | None = Query(default=None, alias="status"),
    user_id: int | None = Query(default=None),
    due_from: datetime | None = Query(default=None),
    due_to: datetime | None = Query(default=None),
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

    expire_overdue_entries(db)
    query = db.query(TaskEntry).filter(TaskEntry.task_id == task_id)

    if current_user.role != UserRole.Admin:
        if current_user.role == UserRole.QC:
            query = query.join(User, TaskEntry.user_id == User.id).filter(
                (TaskEntry.user_id == current_user.id) | (User.qc_id == current_user.id)
            )
        else:
            query = query.filter(TaskEntry.user_id == current_user.id)

    if status_filter is not None:
        query = query.filter(TaskEntry.status == parse_task_status(status_filter))

    if user_id is not None:
        query = query.filter(TaskEntry.user_id == user_id)

    if due_from is not None:
        query = query.filter(TaskEntry.due_at >= due_from)

    if due_to is not None:
        query = query.filter(TaskEntry.due_at <= due_to)

    entries = query.order_by(TaskEntry.start_at.asc(), TaskEntry.id.asc()).all()

    return ListTaskEntriesResponse(
        message="Task entries retrieved successfully.",
        entries=[to_task_entry_summary(entry) for entry in entries],
    )


@router.post("/{task_id}/entries", response_model=TaskEntryResponse)
def create_task_entry(
    task_id: int,
    payload: CreateTaskEntryRequest,
    current_user: User = Depends(require_roles(UserRole.Admin)),
    db: DBSession = Depends(get_db),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found.",
        )

    user_id = payload.user_id or task.user_id
    get_user(user_id, db)
    due_at = payload.due_at or calculate_due_at(task, payload.start_at)
    validate_entry_times(payload.start_at, due_at)

    entry = make_entry(
        task,
        start_at=payload.start_at,
        user_id=user_id,
        due_at=due_at,
    )

    db.add(entry)
    db.commit()
    db.refresh(entry)
    expire_entry_for_request(entry, db)

    return TaskEntryResponse(
        message="Task entry created successfully.",
        entry=to_task_entry_summary(entry),
    )


@router.post("/{task_id}/entries/generate", response_model=GenerateTaskEntriesResponse)
def generate_task_entries(
    task_id: int,
    payload: GenerateTaskEntriesRequest,
    current_user: User = Depends(require_roles(UserRole.Admin)),
    db: DBSession = Depends(get_db),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found.",
        )

    if not task.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive tasks cannot generate entries.",
        )

    last_entry = (
        db.query(TaskEntry)
        .filter(TaskEntry.task_id == task_id)
        .order_by(TaskEntry.start_at.desc(), TaskEntry.id.desc())
        .first()
    )
    next_at = next_start_at(task, last_entry.start_at if last_entry else None)

    entries: list[TaskEntry] = []
    existing_starts = {
        row[0]
        for row in db.query(TaskEntry.start_at)
        .filter(TaskEntry.task_id == task_id)
        .all()
    }

    while next_at is not None and len(entries) < payload.occurrences:
        if next_at not in existing_starts:
            entry = make_entry(task, start_at=next_at)
            db.add(entry)
            db.flush()
            entries.append(entry)
            existing_starts.add(next_at)
        next_at = next_start_at(task, next_at)

    db.commit()
    expire_overdue_entries(db)
    for entry in entries:
        db.refresh(entry)

    return GenerateTaskEntriesResponse(
        message="Task entries generated successfully.",
        entries=[to_task_entry_summary(entry) for entry in entries],
    )


@router.get("/entries/{entry_id}", response_model=TaskEntryResponse)
def get_task_entry(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    entry = db.query(TaskEntry).filter(TaskEntry.id == entry_id).first()
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task entry not found.",
        )

    if not can_access_entry(entry, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this task entry.",
        )

    expire_entry_for_request(entry, db)

    return TaskEntryResponse(
        message="Task entry retrieved successfully.",
        entry=to_task_entry_summary(entry),
    )


@router.patch("/entries/{entry_id}", response_model=TaskEntryResponse)
def update_task_entry(
    entry_id: int,
    payload: UpdateTaskEntryRequest,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    entry = db.query(TaskEntry).filter(TaskEntry.id == entry_id).first()
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task entry not found.",
        )

    if not can_access_entry(entry, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this task entry.",
        )

    expire_entry_for_request(entry, db)

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update.",
        )

    next_status = validate_task_entry_update(entry, update_data, current_user)

    if "user_id" in update_data:
        get_user(update_data["user_id"], db)
        entry.user_id = update_data["user_id"]

    for field in (
        "start_at",
        "due_at",
        "submission_remark",
        "review_remark",
        "evidence",
    ):
        if field in update_data:
            setattr(entry, field, update_data[field])

    validate_entry_times(entry.start_at, entry.due_at)

    if next_status is not None:
        entry.status = next_status
        if entry.status in (TaskStatus.Completed, TaskStatus.Failed):
            if entry.submitted_at is None:
                entry.submitted_at = datetime.now()
            entry.submitted_by_user_id = current_user.id

        if entry.status in (TaskStatus.Approved, TaskStatus.Rejected):
            if entry.reviewed_at is None:
                entry.reviewed_at = datetime.now()
            entry.reviewed_by_user_id = current_user.id

    db.commit()
    db.refresh(entry)

    return TaskEntryResponse(
        message="Task entry updated successfully.",
        entry=to_task_entry_summary(entry),
    )


@router.delete("/entries/{entry_id}", response_model=MessageResponse)
def delete_task_entry(
    entry_id: int,
    current_user: User = Depends(require_roles(UserRole.Admin)),
    db: DBSession = Depends(get_db),
):
    entry = db.query(TaskEntry).filter(TaskEntry.id == entry_id).first()
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task entry not found.",
        )

    db.delete(entry)
    db.commit()

    return MessageResponse(message="Task entry deleted successfully.")
