from datetime import datetime, timezone
from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.case import Case
from app.models.enums import (
    ProofRequestAction,
    ProofRequestStatus,
    ProofSubmissionStatus,
    ValidationType,
)
from app.models.proof_request import ProofRequest
from app.models.proof_request_history import ProofRequestHistory
from app.models.proof_submission import ProofSubmission
from app.models.property_profile import PropertyProfile
from app.services.property_profile_service import PropertyProfileService
from app.services.risk.risk_engine import RiskEngine
from app.services.validation.database_validator import DatabaseValidator
from app.services.validation.gis_validator import GISValidator


class ProofRevalidationService:
    """Service executing complete end-to-end case revalidation upon civilian proof document processing completion."""

    @staticmethod
    async def revalidate_case_after_proof(
        db: AsyncSession,
        case_id: uuid.UUID,
        proof_submission_id: uuid.UUID,
    ) -> bool:
        """Refresh property profile, run new database & GIS validations, generate fresh mismatches, and calculate updated risk assessment."""
        # 1. Fetch submission and associated request
        sub_stmt = select(ProofSubmission).where(ProofSubmission.id == proof_submission_id)
        sub_res = await db.execute(sub_stmt)
        submission = sub_res.scalar_one_or_none()
        if not submission:
            logger.error("Proof submission %s not found for revalidation.", proof_submission_id)
            return False

        req_stmt = select(ProofRequest).where(ProofRequest.id == submission.proof_request_id)
        req_res = await db.execute(req_stmt)
        proof_request = req_res.scalar_one_or_none()

        try:
            logger.info("Starting revalidation pipeline for case %s after proof submission %s.", case_id, proof_submission_id)

            # 2. Refresh property profile with newly extracted proof fields
            profile, _ = await PropertyProfileService.generate_profile(
                db=db,
                case_id=case_id,
                force_refresh=True,
            )

            # 3. Re-run Database Validation
            db_run = await PropertyProfileService.create_validation_run(
                db=db,
                property_profile_id=profile.id,
                validation_type=ValidationType.DATABASE,
            )
            db_validator = DatabaseValidator(db)
            db_status, db_results, db_candidates = await db_validator.validate_run(
                run=db_run,
                profile=profile,
            )
            db_run.status = db_status
            db_run.completed_at = datetime.now(timezone.utc)
            for r in db_results:
                db.add(r)
            for c in db_candidates:
                db.add(c)
            await db.flush()

            # 4. Re-run GIS Validation
            gis_run = await PropertyProfileService.create_validation_run(
                db=db,
                property_profile_id=profile.id,
                validation_type=ValidationType.GIS,
            )
            gis_validator = GISValidator(db)
            gis_status, gis_results = await gis_validator.validate_run(
                run=gis_run,
                profile=profile,
            )
            gis_run.status = gis_status
            gis_run.completed_at = datetime.now(timezone.utc)
            for gr in gis_results:
                db.add(gr)
            await db.flush()

            # 5. Re-run Risk Engine (which synthesizes mismatches and computes new RiskAssessment)
            await RiskEngine.calculate_case_risk(
                db=db,
                case_id=case_id,
                require_jurisdiction=False,
            )

            # 6. Mark submission as PROCESSED
            submission.status = ProofSubmissionStatus.PROCESSED
            now = datetime.now(timezone.utc)

            # Record audit history
            if proof_request:
                audit = ProofRequestHistory(
                    id=uuid.uuid4(),
                    proof_request_id=proof_request.id,
                    actor_id=None,
                    actor_type="system",
                    action=ProofRequestAction.PROCESSING_COMPLETED,
                    old_status=proof_request.status,
                    new_status=proof_request.status,
                    reason="Proof document processing, property profile refresh, and revalidation completed successfully.",
                    created_at=now,
                )
                db.add(audit)

            await db.commit()
            logger.info("Case %s revalidation completed successfully.", case_id)
            return True

        except Exception as exc:
            logger.error("Error during case %s revalidation: %s", case_id, exc, exc_info=True)
            await db.rollback()
            # Mark submission failed in separate transaction
            try:
                sub_res2 = await db.execute(select(ProofSubmission).where(ProofSubmission.id == proof_submission_id))
                sub2 = sub_res2.scalar_one_or_none()
                if sub2:
                    sub2.status = ProofSubmissionStatus.FAILED
                    if proof_request:
                        audit_fail = ProofRequestHistory(
                            id=uuid.uuid4(),
                            proof_request_id=proof_request.id,
                            actor_id=None,
                            actor_type="system",
                            action=ProofRequestAction.PROCESSING_FAILED,
                            old_status=proof_request.status,
                            new_status=proof_request.status,
                            reason=f"Proof document processing or revalidation encountered an error: {str(exc)}",
                            created_at=datetime.now(timezone.utc),
                        )
                        db.add(audit_fail)
                    await db.commit()
            except Exception as inner_exc:
                logger.error("Failed to update proof submission failure status: %s", inner_exc)
            return False
