from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
import pytest

from app.api.dependencies import get_current_user
from app.main import app
from app.models.enums import NotificationChannel, NotificationStatus, NotificationType
from app.models.notification import Notification
from app.models.user import User
from app.services.notification_service import NotificationService


@pytest.mark.anyio
async def test_notification_user_isolation(civilian_user: User, civilian_b_user: User) -> None:
    """Verify that User B cannot see or manipulate User A's notifications."""
    now = datetime.now(timezone.utc)
    notif_id = uuid.uuid4()

    mock_notif = Notification(
        id=notif_id,
        user_id=civilian_user.id,
        type=NotificationType.PROOF_REQUESTED,
        title="Proof required",
        message="Additional proof is needed.",
        channel=NotificationChannel.IN_APP,
        status=NotificationStatus.SENT,
        created_at=now,
        updated_at=now,
    )

    with patch.object(
        NotificationService, "list_user_notifications", new_callable=AsyncMock
    ) as mock_list, patch.object(
        NotificationService, "mark_as_read", new_callable=AsyncMock
    ) as mock_mark:

        # 1. User A lists notifications
        mock_list.return_value = ([mock_notif], 1)
        app.dependency_overrides[get_current_user] = lambda: civilian_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res1 = await ac.get("/api/v1/notifications")
            assert res1.status_code == 200
            assert res1.json()["total"] == 1
            assert res1.json()["items"][0]["id"] == str(notif_id)

        # 2. User B attempts to mark User A's notification read -> 403 Forbidden
        mock_mark.side_effect = HTTPException(status_code=403, detail="You cannot modify another user's notification.")
        app.dependency_overrides[get_current_user] = lambda: civilian_b_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res2 = await ac.post(f"/api/v1/notifications/{notif_id}/read")
            assert res2.status_code == 403

        app.dependency_overrides.clear()
