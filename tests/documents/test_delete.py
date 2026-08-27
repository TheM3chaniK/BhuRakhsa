from unittest.mock import AsyncMock, patch
import uuid

from fastapi import HTTPException
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.user import User
from app.services.document_service import DocumentService


@pytest.mark.anyio
async def test_document_delete_flow(
    civilian_user: User, civilian_b_user: User
) -> None:
    """Verify document deletion rules: allowed for draft case owner, rejected otherwise."""
    doc_id = uuid.uuid4()

    with patch.object(
        DocumentService, "delete_document", new_callable=AsyncMock
    ) as mock_del:
        mock_del.return_value = None

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            # 1. Owner deletes document in DRAFT case -> 200 OK
            app.dependency_overrides[get_current_user] = lambda: civilian_user
            res1 = await ac.delete(f"/api/v1/documents/{doc_id}")
            assert res1.status_code == 200
            assert "deleted successfully" in res1.json()["message"]

            # 2. Deletion attempted on submitted case -> 409 Conflict
            mock_del.side_effect = HTTPException(
                status_code=409,
                detail="Documents can only be deleted while the case is in draft status.",
            )
            res2 = await ac.delete(f"/api/v1/documents/{doc_id}")
            assert res2.status_code == 409

            # 3. Non-owner attempting delete -> 403 Forbidden
            mock_del.side_effect = HTTPException(
                status_code=403,
                detail="Only the case owner can delete this document.",
            )
            app.dependency_overrides[get_current_user] = lambda: civilian_b_user
            res3 = await ac.delete(f"/api/v1/documents/{doc_id}")
            assert res3.status_code == 403

    app.dependency_overrides.clear()
