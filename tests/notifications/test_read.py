from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid
from httpx import ASGITransport, AsyncClient
import pytest

from app.api.dependencies import get_current_user
from app.main import app
from app.models.enums import NotificationChannel, NotificationStatus, NotificationType
from app.models.notification import Notification
from app.models.user import User
from app.services.notification_service import NotificationService


@pytest.mark.anyio
async def test_mark_read_and_unread_count(civilian_user: User) -> None:
    """Verify unread count, marking single notification as read, and marking all read."""
    now = datetime.now(timezone.utc)
    n1_id = uuid.uuid4()

    mock_n1_read = Notification(
        id=n1_id,
        user_id=civilian_user.id,
        type=NotificationType.PROOF_ACCEPTED,
        title="Proof accepted",
        message="Your proof was accepted.",
        channel=NotificationChannel.IN_APP,
        status=NotificationStatus.READ,
        read_at=now,
        created_at=now,
        updated_at=now,
    )

    with patch.object(
        NotificationService, "get_unread_count", new_callable=AsyncMock
    ) as mock_unread, patch.object(
        NotificationService, "mark_as_read", new_callable=AsyncMock
    ) as mock_mark, patch.object(
        NotificationService, "mark_all_as_read", new_callable=AsyncMock
    ) as mock_mark_all:

        app.dependency_overrides[get_current_user] = lambda: civilian_user

        mock_unread.side_effect = [2, 1, 0]
        mock_mark.return_value = mock_n1_read
        mock_mark_all.return_value = 2

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            # 1. Initial unread count -> 2
            res1 = await ac.get("/api/v1/notifications/unread-count")
            assert res1.status_code == 200
            assert res1.json()["count"] == 2

            # 2. Mark n1 read -> 200 OK
            res2 = await ac.post(f"/api/v1/notifications/{n1_id}/read")
            assert res2.status_code == 200
            assert res2.json()["status"] == "read"

            # 3. Unread count -> 1
            res3 = await ac.get("/api/v1/notifications/unread-count")
            assert res3.status_code == 200
            assert res3.json()["count"] == 1

            # 4. Mark all read -> 200 OK
            res4 = await ac.post("/api/v1/notifications/read-all")
            assert res4.status_code == 200

            # 5. Unread count -> 0
            res5 = await ac.get("/api/v1/notifications/unread-count")
            assert res5.status_code == 200
            assert res5.json()["count"] == 0

        app.dependency_overrides.clear()
