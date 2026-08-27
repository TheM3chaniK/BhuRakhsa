from unittest.mock import AsyncMock, patch
import uuid

from fastapi import HTTPException
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.user import User
from app.services.extraction_service import ExtractionService


@pytest.mark.anyio
async def test_extraction_authorization_isolation(
    civilian_b_user: User, officer_b_user: User
) -> None:
    """Verify unauthorized civilian or officer outside case area receives 403 Forbidden on extraction & evidence."""
    doc_id = uuid.uuid4()

    with patch.object(
        ExtractionService, "queue_extraction", new_callable=AsyncMock
    ) as mock_queue, patch.object(
        ExtractionService, "get_extraction_results", new_callable=AsyncMock
    ) as mock_get_ext, patch.object(
        ExtractionService, "get_document_evidence", new_callable=AsyncMock
    ) as mock_get_ev:

        mock_queue.side_effect = HTTPException(
            status_code=403,
            detail="You do not have permission to access this case.",
        )
        mock_get_ext.side_effect = HTTPException(
            status_code=403,
            detail="You do not have permission to access this case.",
        )
        mock_get_ev.side_effect = HTTPException(
            status_code=403,
            detail="You do not have permission to access this case.",
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            # 1. Other civilian attempting to queue extraction -> 403 Forbidden
            app.dependency_overrides[get_current_user] = lambda: civilian_b_user
            res_civ_b = await ac.post(f"/api/v1/documents/{doc_id}/extract")
            assert res_civ_b.status_code == 403

            # 2. Officer outside area attempting to view fields -> 403 Forbidden
            app.dependency_overrides[get_current_user] = lambda: officer_b_user
            res_off_b = await ac.get(f"/api/v1/documents/{doc_id}/extraction")
            assert res_off_b.status_code == 403

            # 3. Officer outside area attempting to view evidence -> 403 Forbidden
            res_off_ev = await ac.get(f"/api/v1/documents/{doc_id}/evidence")
            assert res_off_ev.status_code == 403

    app.dependency_overrides.clear()
