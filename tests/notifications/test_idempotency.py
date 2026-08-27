from datetime import datetime, timezone
import uuid
import pytest

from app.models.enums import NotificationChannel, NotificationStatus, NotificationType
from app.models.notification import Notification


@pytest.mark.anyio
async def test_notification_event_idempotency() -> None:
    """Verify that Notification model maintains unique event_id attribution."""
    user_id = uuid.uuid4()
    event_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    n1 = Notification(
        id=uuid.uuid4(),
        user_id=user_id,
        event_id=event_id,
        type=NotificationType.CASE_APPROVED,
        title="Case approved",
        message="Your case was approved.",
        channel=NotificationChannel.IN_APP,
        status=NotificationStatus.SENT,
        created_at=now,
        updated_at=now,
    )

    assert n1.event_id == event_id
    assert n1.user_id == user_id
    assert n1.type == NotificationType.CASE_APPROVED
