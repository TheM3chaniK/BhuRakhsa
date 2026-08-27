from unittest.mock import AsyncMock
import uuid
import pytest

from app.models.enums import AuditAction, AuditActorType
from app.services.audit_service import AuditService


@pytest.mark.anyio
async def test_audit_event_creation() -> None:
    """Verify that record_audit_event persists append-only audit records with metadata."""
    case_id = uuid.uuid4()
    actor_id = uuid.uuid4()

    mock_db = AsyncMock()

    event = await AuditService.record_audit_event(
        db=mock_db,
        action=AuditAction.RISK_CALCULATED,
        case_id=case_id,
        actor_id=actor_id,
        actor_type=AuditActorType.SYSTEM,
        entity_type="risk_assessment",
        entity_id=uuid.uuid4(),
        old_state="calculating",
        new_state="completed",
        metadata_json={"risk_score": 45, "risk_level": "medium"},
    )

    assert event is not None
    assert event.action == AuditAction.RISK_CALCULATED
    assert event.actor_type == AuditActorType.SYSTEM
    assert event.metadata_json["risk_score"] == 45
    assert mock_db.add.called
    assert mock_db.flush.called
