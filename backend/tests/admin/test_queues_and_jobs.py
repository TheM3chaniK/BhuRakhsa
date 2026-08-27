from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid
from httpx import ASGITransport, AsyncClient
import pytest

from app.api.dependencies import get_current_user
from app.main import app
from app.models.user import User
from app.schemas.admin_dashboard import (
    FailedJobListResponse,
    FailedJobResponse,
    JobRetryResponse,
    QueueMonitoringResponse,
    QueueSummaryItem,
)
from app.services.admin_dashboard_service import AdminDashboardService


@pytest.mark.anyio
async def test_queues_and_failed_jobs(super_admin_user: User) -> None:
    """Verify queue monitoring, failed job listing, and manual job retry."""
    job_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_queues = QueueMonitoringResponse(
        ocr=QueueSummaryItem(pending=2, processing=1, failed=0),
        extraction=QueueSummaryItem(pending=1, processing=0, failed=0),
        validation=QueueSummaryItem(pending=0, processing=0, failed=0),
        gis=QueueSummaryItem(pending=0, processing=0, failed=0),
        revalidation=QueueSummaryItem(pending=0, processing=0, failed=0),
        outbox=QueueSummaryItem(pending=5, processing=1, failed=1),
    )

    mock_failed_jobs = FailedJobListResponse(
        items=[
            FailedJobResponse(
                job_id=job_id,
                job_type="ocr_document_processing",
                case_id=uuid.uuid4(),
                status="failed",
                attempt_count=3,
                created_at=now,
                updated_at=now,
                error_message="Ollama model timeout after 3 attempts.",
            )
        ],
        total=1,
        page=1,
        page_size=20,
    )

    mock_retry_resp = JobRetryResponse(
        job_id=job_id,
        success=True,
        message="Document processing job reset to PENDING for retry.",
    )

    with patch.object(AdminDashboardService, "get_queue_monitoring", new_callable=AsyncMock) as m_q, \
         patch.object(AdminDashboardService, "get_failed_jobs", new_callable=AsyncMock) as m_failed, \
         patch.object(AdminDashboardService, "retry_failed_job", new_callable=AsyncMock) as m_retry:

        m_q.return_value = mock_queues
        m_failed.return_value = mock_failed_jobs
        m_retry.return_value = mock_retry_resp

        app.dependency_overrides[get_current_user] = lambda: super_admin_user
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # 1. Queues
            res_q = await ac.get("/api/v1/admin/queues")
            assert res_q.status_code == 200
            assert res_q.json()["ocr"]["pending"] == 2
            assert res_q.json()["outbox"]["pending"] == 5

            # 2. Failed jobs
            res_failed = await ac.get("/api/v1/admin/jobs/failed")
            assert res_failed.status_code == 200
            assert res_failed.json()["total"] == 1
            assert res_failed.json()["items"][0]["job_type"] == "ocr_document_processing"

            # 3. Retry job
            res_retry = await ac.post(f"/api/v1/admin/jobs/{job_id}/retry")
            assert res_retry.status_code == 200
            assert res_retry.json()["success"] is True

        app.dependency_overrides.clear()
