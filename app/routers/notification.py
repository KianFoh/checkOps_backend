from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session as DBSession

from app.database import SessionLocal
from app.helpers.notifications import publish_notification_read
from app.helpers.notifications import publish_notifications_read_all
from app.helpers.security import get_current_user
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import ListNotificationsResponse
from app.schemas.notification import MessageResponse
from app.schemas.notification import NotificationResponse
from app.schemas.notification import NotificationSummary

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def to_notification_summary(notification: Notification) -> NotificationSummary:
    return NotificationSummary(
        id=notification.id,
        user_id=notification.user_id,
        title=notification.title,
        message=notification.message,
        type=notification.type,
        related_task_id=notification.related_task_id,
        related_task_entry_id=notification.related_task_entry_id,
        read_at=notification.read_at,
        created_at=notification.created_at,
    )


@router.get("", response_model=ListNotificationsResponse)
def get_notifications(
    unread_only: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    query = db.query(Notification).filter(Notification.user_id == current_user.id)

    if unread_only:
        query = query.filter(Notification.read_at.is_(None))

    notifications = query.order_by(Notification.created_at.desc(), Notification.id.desc()).all()

    return ListNotificationsResponse(
        message="Notifications retrieved successfully.",
        notifications=[
            to_notification_summary(notification)
            for notification in notifications
        ],
    )


@router.patch("/read-all", response_model=MessageResponse)
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.read_at.is_(None),
    ).update({Notification.read_at: datetime.now()}, synchronize_session=False)
    db.commit()
    publish_notifications_read_all(current_user.id)

    return MessageResponse(message="Notifications marked as read.")


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
        .first()
    )
    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found.",
        )

    if notification.read_at is None:
        notification.read_at = datetime.now()
        db.commit()
        db.refresh(notification)
        publish_notification_read(notification)

    return NotificationResponse(
        message="Notification marked as read.",
        notification=to_notification_summary(notification),
    )
