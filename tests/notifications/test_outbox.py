from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest

from app.models.enums import OutboxEventStatus
from app.models.outbox_event import OutboxEvent
from app.workers.outbox_worker import HANDLERS, OutboxWorker


@pytest.mark.anyio
async def test_outbox_worker_processes_event_and_creates_notification() -> None:
    """Verify that OutboxWorker reads pending events, invokes handlers, and updates event status."""
    now = datetime.now(timezone.utc)
    case_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    event_id = uuid.uuid4()

    mock_event = OutboxEvent(
        id=event_id,
        event_type="CaseApprovedEvent",
        aggregate_type="case",
        aggregate_id=case_id,
        payload={
            "case_id": str(case_id),
            "review_id": str(uuid.uuid4()),
            "decided_by": str(uuid.uuid4()),
            "owner_id": str(owner_id),
            "reason": "Satisfactory verification completed.",
            "risk_score": 10,
            "risk_level": "low",
        },
        status=OutboxEventStatus.PENDING,
        attempt_count=0,
        available_at=now,
        created_at=now,
        updated_at=now,
    )

    mock_db = AsyncMock()
    mock_db.execute.return_value = MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_event]))))

    mock_handler = AsyncMock()
    original_handler = HANDLERS.get("CaseApprovedEvent")
    HANDLERS["CaseApprovedEvent"] = mock_handler
    try:
        processed_count = await OutboxWorker.process_batch(db=mock_db, limit=10)

        assert processed_count == 1
        assert mock_event.status == OutboxEventStatus.PROCESSED
        assert mock_event.processed_at is not None
        assert mock_handler.called
        assert mock_db.commit.called
    finally:
        if original_handler:
            HANDLERS["CaseApprovedEvent"] = original_handler
