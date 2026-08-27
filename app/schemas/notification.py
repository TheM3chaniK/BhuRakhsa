from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict

from app.models.enums import NotificationChannel, NotificationStatus, NotificationType


class NotificationResponse(BaseModel):
    """User in-app notification message schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    case_id: Optional[uuid.UUID] = None
    type: NotificationType
    title: str
    message: str
    channel: NotificationChannel
    status: NotificationStatus
    data: Optional[Dict[str, Any]] = None
    read_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    created_at: datetime


class NotificationListResponse(BaseModel):
    """Paginated list of user notifications."""

    items: List[NotificationResponse]
    total: int
    page: int
    page_size: int


class UnreadCountResponse(BaseModel):
    """Unread notifications count."""

    count: int
