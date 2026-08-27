from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.events.handlers import HANDLERS
from app.models.enums import OutboxEventStatus
from app.models.outbox_event import OutboxEvent


class OutboxWorker:
    """Worker processing pending outbox domain events and delivering notifications idempotently."""

    MAX_ATTEMPTS = 5

    @classmethod
    async def process_batch(cls, db: AsyncSession, limit: int = 50) -> int:
        """Fetch and process a batch of pending outbox events."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(OutboxEvent)
            .where(
                OutboxEvent.status == OutboxEventStatus.PENDING,
                OutboxEvent.available_at <= now,
            )
            .order_by(OutboxEvent.created_at.asc())
            .limit(limit)
        )
        res = await db.execute(stmt)
        events = list(res.scalars().all())

        processed_count = 0
        for ev in events:
            ev.status = OutboxEventStatus.PROCESSING
            await db.flush()

            handler = HANDLERS.get(ev.event_type)
            if not handler:
                logger.warning("No registered handler for outbox event %s (%s). Marking processed.", ev.id, ev.event_type)
                ev.status = OutboxEventStatus.PROCESSED
                ev.processed_at = now
                processed_count += 1
                continue

            try:
                await handler(db=db, payload=ev.payload, event_id=ev.id)
                ev.status = OutboxEventStatus.PROCESSED
                ev.processed_at = datetime.now(timezone.utc)
                ev.error_message = None
                processed_count += 1
                logger.info("Successfully processed outbox event %s (%s).", ev.id, ev.event_type)
            except Exception as exc:
                ev.attempt_count += 1
                logger.error("Error processing outbox event %s (attempt %d): %s", ev.id, ev.attempt_count, exc, exc_info=True)
                if ev.attempt_count >= cls.MAX_ATTEMPTS:
                    ev.status = OutboxEventStatus.FAILED
                    ev.error_message = f"Max retries exceeded: {str(exc)}"
                else:
                    ev.status = OutboxEventStatus.PENDING
                    # Exponential backoff: 2^attempts minutes
                    delay_seconds = (2 ** ev.attempt_count) * 60
                    ev.available_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
                    ev.error_message = str(exc)

        await db.commit()
        return processed_count
