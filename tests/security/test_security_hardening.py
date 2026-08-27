from unittest.mock import AsyncMock, MagicMock, patch
import uuid
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
import pytest

from app.core.middleware import limiter
from app.main import app
from app.models.case import Case
from app.models.enums import AuditActorType, CaseStatus
from app.services.case_state_machine import CaseStateMachine


@pytest.mark.anyio
async def test_security_headers_and_correlation_id() -> None:
    """Verify security headers and correlation IDs are present on all responses."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/health")
        assert res.status_code == 200
        assert "X-Request-ID" in res.headers
        assert res.headers["X-Content-Type-Options"] == "nosniff"
        assert res.headers["X-Frame-Options"] == "DENY"
        assert res.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


@pytest.mark.anyio
async def test_rate_limiter_throttles_excessive_logins() -> None:
    """Verify in-memory sliding-window rate limiter throttles excessive requests to sensitive routes."""
    limiter.clear()
    with patch("app.services.auth_service.AuthService.authenticate_user", new_callable=AsyncMock) as mock_auth:
        mock_auth.side_effect = HTTPException(status_code=401, detail="Invalid email or password.")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # Send 11 rapid login attempts
            responses = []
            for _ in range(11):
                res = await ac.post(
                    "/api/v1/auth/login",
                    json={"email": "spam@example.com", "password": "wrongpassword"},
                )
                responses.append(res.status_code)

            # 11th request must be throttled with 429 Too Many Requests
            assert 429 in responses
    limiter.clear()


@pytest.mark.anyio
async def test_case_state_machine_transitions() -> None:
    """Verify deterministic state machine allows legal transitions and blocks illegal/terminal ones."""
    # Legal transitions
    assert CaseStateMachine.can_transition(CaseStatus.DRAFT, CaseStatus.SUBMITTED) is True
    assert CaseStateMachine.can_transition(CaseStatus.SUBMITTED, CaseStatus.PROCESSING) is True
    assert CaseStateMachine.can_transition(CaseStatus.PROCESSING, CaseStatus.REVIEW_READY) is True
    assert CaseStateMachine.can_transition(CaseStatus.REVIEW_READY, CaseStatus.UNDER_REVIEW) is True
    assert CaseStateMachine.can_transition(CaseStatus.UNDER_REVIEW, CaseStatus.APPROVED) is True
    assert CaseStateMachine.can_transition(CaseStatus.UNDER_REVIEW, CaseStatus.REJECTED) is True
    assert CaseStateMachine.can_transition(CaseStatus.UNDER_REVIEW, CaseStatus.PROOF_REQUIRED) is True
    assert CaseStateMachine.can_transition(CaseStatus.PROOF_REQUIRED, CaseStatus.REVIEW_READY) is True

    # Illegal transitions
    assert CaseStateMachine.can_transition(CaseStatus.DRAFT, CaseStatus.APPROVED) is False
    assert CaseStateMachine.can_transition(CaseStatus.SUBMITTED, CaseStatus.APPROVED) is False
    assert CaseStateMachine.can_transition(CaseStatus.APPROVED, CaseStatus.UNDER_REVIEW) is False
    assert CaseStateMachine.can_transition(CaseStatus.REJECTED, CaseStatus.DRAFT) is False

    # Transition execution on terminal case raises 409
    mock_db = AsyncMock()
    terminal_case = Case(
        id=uuid.uuid4(),
        case_number="CASE-2026-000099",
        status=CaseStatus.APPROVED,
    )
    with pytest.raises(HTTPException) as exc_info:
        await CaseStateMachine.transition(
            db=mock_db,
            case=terminal_case,
            target_status=CaseStatus.UNDER_REVIEW,
            actor_id=uuid.uuid4(),
            actor_type=AuditActorType.USER,
        )
    assert exc_info.value.status_code == 409
