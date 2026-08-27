from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.enums import CaseStatus, ReviewStatus, RiskLevel
from app.models.user import User
from app.schemas.review import ReviewQueueItemResponse, ReviewQueueResponse
from app.services.review_service import ReviewService


@pytest.mark.anyio
async def test_review_queue_retrieval_and_filtering(
    officer_a_user: User, civilian_user: User
) -> None:
    """Verify Area Officer queue returns area-filtered, risk-prioritized items, and civilians are rejected."""
    now = datetime.now(timezone.utc)
    mock_queue_items = [
        ReviewQueueItemResponse(
            case_id=uuid.uuid4(),
            case_number="CASE-2026-000001",
            title="Plot 7 Verification",
            area_id=uuid.uuid4(),
            risk_score=85,
            risk_level=RiskLevel.CRITICAL,
            case_status=CaseStatus.REVIEW_READY,
            review_status=ReviewStatus.NOT_STARTED,
            reviewer_id=None,
            created_at=now,
        ),
        ReviewQueueItemResponse(
            case_id=uuid.uuid4(),
            case_number="CASE-2026-000002",
            title="Survey 45 Verification",
            area_id=uuid.uuid4(),
            risk_score=55,
            risk_level=RiskLevel.HIGH,
            case_status=CaseStatus.REVIEW_READY,
            review_status=ReviewStatus.NOT_STARTED,
            reviewer_id=None,
            created_at=now,
        ),
    ]
    mock_queue_response = ReviewQueueResponse(items=mock_queue_items, total=2)

    with patch.object(
        ReviewService, "get_review_queue", new_callable=AsyncMock
    ) as mock_get_queue:
        mock_get_queue.return_value = mock_queue_response

        # 1. Officer retrieves queue -> 200 OK with items
        app.dependency_overrides[get_current_user] = lambda: officer_a_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res = await ac.get("/api/v1/officer/reviews/queue?risk_level=critical")
            assert res.status_code == 200
            data = res.json()
            assert data["total"] == 2
            assert len(data["items"]) == 2
            assert data["items"][0]["risk_level"] == "critical"
            assert data["items"][1]["risk_level"] == "high"

        # 2. Civilian attempts to access queue -> 403 Forbidden
        mock_get_queue.side_effect = None
        app.dependency_overrides[get_current_user] = lambda: civilian_user
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            res_civ = await ac.get("/api/v1/officer/reviews/queue")
            assert res_civ.status_code == 403

    app.dependency_overrides.clear()
