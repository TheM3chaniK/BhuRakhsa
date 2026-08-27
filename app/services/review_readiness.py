from typing import Optional, Tuple
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case
from app.models.document import Document
from app.models.enums import DocumentStatus, RiskAssessmentStatus, ValidationStatus, ValidationType
from app.models.property_profile import PropertyProfile
from app.models.risk_assessment import RiskAssessment
from app.models.validation import ValidationRun


class ReviewReadinessService:
    """Service evaluating whether a case has completed all pipeline prerequisites before officer review."""

    @staticmethod
    async def is_ready_for_review(
        db: AsyncSession, case_id: uuid.UUID
    ) -> Tuple[bool, Optional[str]]:
        """Verify that OCR, extraction, profile generation, validation runs, and risk assessment are complete."""
        case_stmt = select(Case).where(Case.id == case_id)
        case_res = await db.execute(case_stmt)
        case = case_res.scalar_one_or_none()
        if not case:
            return False, "Case not found."

        # 1. Documents check
        docs_stmt = select(Document).where(
            Document.case_id == case_id,
            Document.deleted_at.is_(None),
        )
        docs_res = await db.execute(docs_stmt)
        documents = list(docs_res.scalars().all())
        if not documents:
            return False, "No uploaded documents found for case."

        unprocessed = [d for d in documents if d.status != DocumentStatus.PROCESSED]
        if unprocessed:
            return False, f"{len(unprocessed)} document(s) have not completed OCR and extraction."

        # 2. Property profile check
        prof_stmt = select(PropertyProfile).where(PropertyProfile.case_id == case_id)
        prof_res = await db.execute(prof_stmt)
        profile = prof_res.scalar_one_or_none()
        if not profile:
            return False, "Property profile has not been generated for this case."

        # 3. Database validation run check
        db_val_stmt = (
            select(ValidationRun)
            .where(
                ValidationRun.property_profile_id == profile.id,
                ValidationRun.validation_type == ValidationType.DATABASE,
            )
            .order_by(ValidationRun.created_at.desc())
        )
        db_val_res = await db.execute(db_val_stmt)
        db_run = db_val_res.scalars().first()
        if not db_run or db_run.status in (ValidationStatus.PENDING, ValidationStatus.RUNNING):
            return False, "Government database validation has not completed."

        # 4. GIS validation run check
        gis_val_stmt = (
            select(ValidationRun)
            .where(
                ValidationRun.property_profile_id == profile.id,
                ValidationRun.validation_type == ValidationType.GIS,
            )
            .order_by(ValidationRun.created_at.desc())
        )
        gis_val_res = await db.execute(gis_val_stmt)
        gis_run = gis_val_res.scalars().first()
        if not gis_run or gis_run.status in (ValidationStatus.PENDING, ValidationStatus.RUNNING):
            return False, "GIS spatial validation has not completed."

        # 5. Risk assessment check
        risk_stmt = (
            select(RiskAssessment)
            .where(
                RiskAssessment.case_id == case_id,
                RiskAssessment.status == RiskAssessmentStatus.COMPLETED,
            )
            .order_by(RiskAssessment.calculated_at.desc())
        )
        risk_res = await db.execute(risk_stmt)
        risk_assessment = risk_res.scalars().first()
        if not risk_assessment:
            return False, "Risk assessment has not been calculated for this case."

        return True, None
