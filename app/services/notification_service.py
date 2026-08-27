from datetime import datetime, timezone
from typing import List, Optional, Tuple
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import NotificationStatus
from app.models.notification import Notification


class NotificationService:
    """Service providing in-app notification queries, unread counts, and read status management."""

    @staticmethod
    async def list_user_notifications(
        db: AsyncSession,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        status_filter: Optional[NotificationStatus] = None,
    ) -> Tuple[List[Notification], int]:
        """Fetch paginated notifications for the requesting user."""
        stmt = select(Notification).where(Notification.user_id == user_id)
        if status_filter:
            stmt = stmt.where(Notification.status == status_filter)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_res = await db.execute(count_stmt)
        total = count_res.scalar() or 0

        # Paginate
        offset = (page - 1) * page_size
        stmt = stmt.order_by(Notification.created_at.desc()).offset(offset).limit(page_size)
        res = await db.execute(stmt)
        return list(res.scalars().all()), total

    @staticmethod
    async def get_unread_count(db: AsyncSession, user_id: uuid.UUID) -> int:
        """Count unread notifications for the user."""
        stmt = (
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.status.in_([NotificationStatus.SENT, NotificationStatus.PENDING]),
                Notification.read_at.is_(None),
            )
        )
        res = await db.execute(stmt)
        return res.scalar() or 0

    @staticmethod
    async def mark_as_read(
        db: AsyncSession,
        notification_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Notification:
        """Mark a single notification as read."""
        stmt = select(Notification).where(Notification.id == notification_id)
        res = await db.execute(stmt)
        notif = res.scalar_one_or_none()
        if not notif:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found.",
            )

        if notif.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot modify another user's notification.",
            )

        if notif.status != NotificationStatus.READ:
            notif.status = NotificationStatus.READ
            notif.read_at = datetime.now(timezone.utc)
            await db.commit()
            await db.refresh(notif)

        return notif

    @staticmethod
    async def mark_all_as_read(db: AsyncSession, user_id: uuid.UUID) -> int:
        """Mark all unread notifications as read for a user."""
        now = datetime.now(timezone.utc)
        stmt = (
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.status != NotificationStatus.READ,
            )
            .values(
                status=NotificationStatus.READ,
                read_at=now,
                updated_at=now,
            )
        )
        res = await db.execute(stmt)
        await db.commit()
        return res.rowcount or 0
