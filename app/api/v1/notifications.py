from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.enums import NotificationStatus
from app.models.user import User
from app.schemas.notification import (
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
)
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["In-App Notifications"])


@router.get(
    "",
    response_model=NotificationListResponse,
    status_code=status.HTTP_200_OK,
    summary="List User Notifications",
    description="Retrieve paginated in-app notifications for the authenticated user, ordered newest first.",
)
async def list_notifications(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: Optional[NotificationStatus] = Query(None, alias="status", description="Filter by notification status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationListResponse:
    """Fetch user's paginated notifications."""
    items, total = await NotificationService.list_user_notifications(
        db=db,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
    )
    return NotificationListResponse(
        items=[NotificationResponse.model_validate(n) for n in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Unread Notification Count",
    description="Count unread in-app notifications for badge counters.",
)
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UnreadCountResponse:
    """Return count of unread notifications for current user."""
    count = await NotificationService.get_unread_count(
        db=db,
        user_id=current_user.id,
    )
    return UnreadCountResponse(count=count)


@router.post(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark Notification as Read",
    description="Mark a single notification as read. Only the notification owner can perform this operation.",
)
async def mark_notification_read(
    notification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationResponse:
    """Mark single notification as read."""
    notif = await NotificationService.mark_as_read(
        db=db,
        notification_id=notification_id,
        user_id=current_user.id,
    )
    return NotificationResponse.model_validate(notif)


@router.post(
    "/read-all",
    response_model=UnreadCountResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark All Notifications as Read",
    description="Mark all unread notifications as read for the authenticated user.",
)
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UnreadCountResponse:
    """Mark all unread notifications as read."""
    updated = await NotificationService.mark_all_as_read(
        db=db,
        user_id=current_user.id,
    )
    return UnreadCountResponse(count=updated)
