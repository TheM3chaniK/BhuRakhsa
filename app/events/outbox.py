from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import OutboxEventStatus
from app.models.outbox_event import OutboxEvent


class OutboxService:
    """Service writing domain events to the outbox table inside the caller's active database transaction."""

    @staticmethod
    async def record_event(
        db: AsyncSession,
        event_type: str,
        aggregate_type: str,
        aggregate_id: uuid.UUID,
        payload: Dict[str, Any],
        event_id: Optional[uuid.UUID] = None,
    ) -> OutboxEvent:
        """Create a pending outbox event."""
        now = datetime.now(timezone.utc)
        outbox_event = OutboxEvent(
            id=event_id or uuid.uuid4(),
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload,
            status=OutboxEventStatus.PENDING,
            attempt_count=0,
            available_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(outbox_event)
        await db.flush()
        return outbox_event
