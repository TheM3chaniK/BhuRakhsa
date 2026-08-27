from datetime import datetime, timezone
import uuid
import pytest

from app.models.enums import NotificationChannel, NotificationStatus, NotificationType
from app.models.notification import Notification


@pytest.mark.anyio
async def test_notification_creation_and_listing() -> None:
    """Verify that Notification model can be instantiated with valid attributes."""
    user_id = uuid.uuid4()
    case_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    notif = Notification(
        id=uuid.uuid4(),
        user_id=user_id,
        case_id=case_id,
        type=NotificationType.CASE_APPROVED,
        title="Property verification completed",
        message="Your property verification case has been approved.",
        channel=NotificationChannel.IN_APP,
        status=NotificationStatus.SENT,
        data={"action": "open_case"},
        created_at=now,
        updated_at=now,
    )

    assert notif.user_id == user_id
    assert notif.type == NotificationType.CASE_APPROVED
    assert notif.status == NotificationStatus.SENT
    assert notif.title == "Property verification completed"
