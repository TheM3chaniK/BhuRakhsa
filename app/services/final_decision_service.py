from typing import Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.case import Case
from app.models.final_decision import FinalDecision
from app.models.user import User
from app.services.case_access_service import CaseAccessService


class FinalDecisionService:
    """Service retrieving immutable case final determination snapshots."""

    @staticmethod
    async def get_final_decision(
        db: AsyncSession,
        case_id: uuid.UUID,
        user: User,
    ) -> FinalDecision:
        """Fetch final determination snapshot for a case."""
        case_stmt = select(Case).where(Case.id == case_id)
        case_res = await db.execute(case_stmt)
        case = case_res.scalar_one_or_none()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found.",
            )
        await CaseAccessService.verify_case_access(db, user, case)

        stmt = select(FinalDecision).where(FinalDecision.case_id == case_id)
        res = await db.execute(stmt)
        decision = res.scalar_one_or_none()
        if not decision:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No final decision has been recorded for this case.",
            )
        return decision
