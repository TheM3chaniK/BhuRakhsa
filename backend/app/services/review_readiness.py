from datetime import datetime, timezone
from typing import Optional, Tuple
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.case import Case
from app.models.document import Document
from app.models.enums import (
    CaseStatus,
    DocumentStatus,
    RiskAssessmentStatus,
    ValidationStatus,
    ValidationType,
)
from app.models.property_profile import PropertyProfile
from app.models.risk_assessment import RiskAssessment
from app.models.validation import ValidationRun


class ReviewReadinessService:
    """Service evaluating whether a case has completed all pipeline prerequisites before officer review."""

    @staticmethod
    async def execute_automated_pipeline(db: AsyncSession, case_id: uuid.UUID) -> bool:
        """Run property profile assembly, database & GIS validations, and risk assessment automatically for a case."""
        from app.services.property_profile_service import PropertyProfileService
        from app.services.risk.risk_engine import RiskEngine
        from app.services.validation.database_validator import DatabaseValidator
        from app.services.validation.gis_validator import GISValidator

        try:
            # 1. Fetch case
            case_stmt = select(Case).where(Case.id == case_id)
            case_res = await db.execute(case_stmt)
            case = case_res.scalar_one_or_none()
            if not case:
                return False

            # 2. Check documents
            docs_stmt = select(Document).where(
                Document.case_id == case_id,
                Document.deleted_at.is_(None),
            )
            docs_res = await db.execute(docs_stmt)
            documents = list(docs_res.scalars().all())
            if not documents:
                return False

            processed_docs = [d for d in documents if d.status == DocumentStatus.PROCESSED]
            if not processed_docs:
                return False

            # 3. Generate or refresh profile
            prof_res = await db.execute(
                select(PropertyProfile).where(PropertyProfile.case_id == case_id)
            )
            profile = prof_res.scalar_one_or_none()
            if not profile:
                profile = await PropertyProfileService.generate_profile(
                    db=db, case_id=case_id, user=None, force_refresh=True
                )

            if not profile:
                return False

            # 4. Database Validation Run
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
                if not db_run:
                    db_run = ValidationRun(
                        id=uuid.uuid4(),
                        property_profile_id=profile.id,
                        validation_type=ValidationType.DATABASE,
                        status=ValidationStatus.RUNNING,
                        started_at=datetime.now(timezone.utc),
                    )
                    db.add(db_run)
                    await db.flush()
                db_validator = DatabaseValidator(db)
                db_status, db_results, db_candidates = await db_validator.validate_run(
                    run=db_run, profile=profile
                )
                db_run.status = db_status
                db_run.completed_at = datetime.now(timezone.utc)
                for r in db_results:
                    db.add(r)
                for c in db_candidates:
                    db.add(c)
                await db.flush()

            # 5. GIS Validation Run
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
                if not gis_run:
                    gis_run = ValidationRun(
                        id=uuid.uuid4(),
                        property_profile_id=profile.id,
                        validation_type=ValidationType.GIS,
                        status=ValidationStatus.RUNNING,
                        started_at=datetime.now(timezone.utc),
                    )
                    db.add(gis_run)
                    await db.flush()
                gis_validator = GISValidator(db)
                gis_status, gis_results = await gis_validator.validate_run(
                    run=gis_run, profile=profile
                )
                gis_run.status = gis_status
                gis_run.completed_at = datetime.now(timezone.utc)
                for gr in gis_results:
                    db.add(gr)
                await db.flush()

            # 6. Risk Engine
            await RiskEngine.calculate_case_risk(
                db=db, case_id=case_id, require_jurisdiction=False
            )

            # 7. Transition case status to REVIEW_READY if applicable
            if case.status in (CaseStatus.DRAFT, CaseStatus.SUBMITTED, CaseStatus.PROCESSING):
                case.status = CaseStatus.REVIEW_READY
                case.updated_at = datetime.now(timezone.utc)

            await db.commit()
            return True
        except Exception as e:
            logger.exception(
                "Error executing automated pipeline for case %s: %s", case_id, e
            )
            await db.rollback()
            return False

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

        # If profile or downstream runs are missing but documents are processed, run automated pipeline
        if not profile:
            auto_ok = await ReviewReadinessService.execute_automated_pipeline(db, case_id)
            if auto_ok:
                prof_res = await db.execute(
                    select(PropertyProfile).where(PropertyProfile.case_id == case_id)
                )
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
            await ReviewReadinessService.execute_automated_pipeline(db, case_id)
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
            await ReviewReadinessService.execute_automated_pipeline(db, case_id)
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
            await ReviewReadinessService.execute_automated_pipeline(db, case_id)
            risk_res = await db.execute(risk_stmt)
            risk_assessment = risk_res.scalars().first()

        if not risk_assessment:
            return False, "Risk assessment has not been calculated for this case."

        return True, None
