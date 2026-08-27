import asyncio
from unittest.mock import AsyncMock
import uuid
import pytest

from app.models.case import Case
from app.models.enums import AuditActorType, CaseStatus
from app.services.case_state_machine import CaseStateMachine


@pytest.mark.anyio
async def test_case_state_machine_transition_validations() -> None:
    """Verify state machine correctly handles multi-step forward lifecycle paths."""
    mock_db = AsyncMock()
    case = Case(
        id=uuid.uuid4(),
        case_number="CASE-CONCUR-001",
        status=CaseStatus.DRAFT,
    )

    # 1. DRAFT -> SUBMITTED
    await CaseStateMachine.transition(mock_db, case, CaseStatus.SUBMITTED, actor_id=uuid.uuid4())
    assert case.status == CaseStatus.SUBMITTED

    # 2. SUBMITTED -> PROCESSING
    await CaseStateMachine.transition(mock_db, case, CaseStatus.PROCESSING, actor_id=uuid.uuid4())
    assert case.status == CaseStatus.PROCESSING

    # 3. PROCESSING -> REVIEW_READY
    await CaseStateMachine.transition(mock_db, case, CaseStatus.REVIEW_READY, actor_id=uuid.uuid4())
    assert case.status == CaseStatus.REVIEW_READY

    # 4. REVIEW_READY -> UNDER_REVIEW
    await CaseStateMachine.transition(mock_db, case, CaseStatus.UNDER_REVIEW, actor_id=uuid.uuid4())
    assert case.status == CaseStatus.UNDER_REVIEW

    # 5. UNDER_REVIEW -> REJECTED (terminal)
    await CaseStateMachine.transition(mock_db, case, CaseStatus.REJECTED, actor_id=uuid.uuid4())
    assert case.status == CaseStatus.REJECTED

    # 6. Terminal status cannot transition anywhere
    assert CaseStateMachine.can_transition(case.status, CaseStatus.DRAFT) is False
    assert CaseStateMachine.can_transition(case.status, CaseStatus.APPROVED) is False
    assert CaseStateMachine.can_transition(case.status, CaseStatus.UNDER_REVIEW) is False
