from sqlalchemy.orm import Session as DBSession

from app.helpers.realtime import manager
from app.helpers.realtime import publish_task_entry_event
from app.helpers.realtime import serialize_datetime
from app.models.notification import Notification
from app.models.task import TaskEntry
from app.models.user import User
from app.models.user import UserRole


def add_notification(
    db: DBSession,
    user_id: int,
    title: str,
    message: str,
    type: str,
    entry: TaskEntry | None = None,
) -> None:
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        type=type,
        related_task_id=entry.task_id if entry else None,
        related_task_entry_id=entry.id if entry else None,
    )
    db.add(notification)
    db.flush()
    publish_notification_created(notification)


def serialize_notification(notification: Notification) -> dict:
    return {
        "id": notification.id,
        "user_id": notification.user_id,
        "title": notification.title,
        "message": notification.message,
        "type": notification.type,
        "related_task_id": notification.related_task_id,
        "related_task_entry_id": notification.related_task_entry_id,
        "read_at": serialize_datetime(notification.read_at),
        "created_at": serialize_datetime(notification.created_at),
    }


def publish_notification_created(notification: Notification) -> None:
    manager.publish_to_user(
        notification.user_id,
        {
            "event": "notification.created",
            "notification": serialize_notification(notification),
        },
    )


def publish_notification_read(notification: Notification) -> None:
    manager.publish_to_user(
        notification.user_id,
        {
            "event": "notification.read",
            "notification": serialize_notification(notification),
        },
    )


def publish_notifications_read_all(user_id: int) -> None:
    manager.publish_to_user(
        user_id,
        {
            "event": "notifications.read_all",
        },
    )


def add_notifications(
    db: DBSession,
    user_ids: list[int],
    title: str,
    message: str,
    type: str,
    entry: TaskEntry | None = None,
) -> None:
    seen_user_ids: set[int] = set()
    for user_id in user_ids:
        if user_id in seen_user_ids:
            continue
        seen_user_ids.add(user_id)
        add_notification(db, user_id, title, message, type, entry)


def get_admin_user_ids(db: DBSession) -> list[int]:
    return [
        user.id
        for user in db.query(User.id)
        .filter(User.role == UserRole.Admin, User.active == True)
        .all()
    ]


def get_reviewer_user_ids(db: DBSession, entry: TaskEntry) -> list[int]:
    user_ids = get_admin_user_ids(db)
    assigned_user = entry.user
    if (
        assigned_user is not None
        and assigned_user.role == UserRole.Operator
        and assigned_user.qc_id is not None
    ):
        user_ids.append(assigned_user.qc_id)
    return user_ids


def get_task_name(entry: TaskEntry) -> str:
    if entry.task is None:
        return "Task"
    return entry.task.name


def notify_task_entry_assigned(db: DBSession, entry: TaskEntry) -> None:
    task_name = get_task_name(entry)
    add_notification(
        db=db,
        user_id=entry.user_id,
        title="Task entry assigned",
        message=f"You have been assigned to {task_name}.",
        type="TaskEntryAssigned",
        entry=entry,
    )
    publish_task_entry_event(
        [entry.user_id],
        "task_entry.assigned",
        entry.task_id,
        entry.id,
    )


def notify_task_entry_reassigned(
    db: DBSession,
    entry: TaskEntry,
    old_user_id: int,
) -> None:
    task_name = get_task_name(entry)
    add_notifications(
        db=db,
        user_ids=[entry.user_id],
        title="Task entry assigned",
        message=f"You have been assigned to {task_name}.",
        type="TaskEntryReassigned",
        entry=entry,
    )
    add_notifications(
        db=db,
        user_ids=[old_user_id],
        title="Task entry reassigned",
        message=f"You are no longer assigned to {task_name}.",
        type="TaskEntryReassignedFromYou",
        entry=entry,
    )
    publish_task_entry_event(
        [entry.user_id, old_user_id],
        "task_entry.reassigned",
        entry.task_id,
        entry.id,
    )


def notify_task_entry_schedule_updated(db: DBSession, entry: TaskEntry) -> None:
    task_name = get_task_name(entry)
    add_notification(
        db=db,
        user_id=entry.user_id,
        title="Task entry updated",
        message=f"The schedule for {task_name} has been updated.",
        type="TaskEntryScheduleUpdated",
        entry=entry,
    )
    publish_task_entry_event(
        [entry.user_id],
        "task_entry.schedule_updated",
        entry.task_id,
        entry.id,
    )


def notify_task_entry_submitted(db: DBSession, entry: TaskEntry) -> None:
    task_name = get_task_name(entry)
    user_ids = get_reviewer_user_ids(db, entry)
    add_notifications(
        db=db,
        user_ids=user_ids,
        title="Task entry submitted",
        message=f"{task_name} has been submitted for review.",
        type="TaskEntrySubmitted",
        entry=entry,
    )
    publish_task_entry_event(
        user_ids,
        "task_entry.submitted",
        entry.task_id,
        entry.id,
    )


def notify_task_entry_failed(db: DBSession, entry: TaskEntry) -> None:
    task_name = get_task_name(entry)
    user_ids = get_reviewer_user_ids(db, entry)
    add_notifications(
        db=db,
        user_ids=user_ids,
        title="Task entry failed",
        message=f"{task_name} was submitted as failed.",
        type="TaskEntryFailed",
        entry=entry,
    )
    publish_task_entry_event(
        user_ids,
        "task_entry.failed",
        entry.task_id,
        entry.id,
    )


def notify_task_entry_reviewed(db: DBSession, entry: TaskEntry) -> None:
    task_name = get_task_name(entry)
    add_notification(
        db=db,
        user_id=entry.user_id,
        title=f"Task entry {entry.status.value.lower()}",
        message=f"{task_name} has been {entry.status.value.lower()}.",
        type=f"TaskEntry{entry.status.value}",
        entry=entry,
    )
    publish_task_entry_event(
        [entry.user_id],
        f"task_entry.{entry.status.value.lower()}",
        entry.task_id,
        entry.id,
    )


def notify_task_entry_expired(db: DBSession, entry: TaskEntry) -> None:
    task_name = get_task_name(entry)
    user_ids = [entry.user_id] + get_reviewer_user_ids(db, entry)
    add_notifications(
        db=db,
        user_ids=user_ids,
        title="Task entry expired",
        message=f"{task_name} has expired.",
        type="TaskEntryExpired",
        entry=entry,
    )
    publish_task_entry_event(
        user_ids,
        "task_entry.expired",
        entry.task_id,
        entry.id,
    )
