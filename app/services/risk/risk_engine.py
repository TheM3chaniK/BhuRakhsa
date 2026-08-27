from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import uuid

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import logger
from app.models.case import Case
from app.models.enums import (
    MismatchSeverity,
    MismatchType,
    RiskAssessmentStatus,
    RiskLevel,
    UserRole,
    ValidationType,
)
from app.models.evidence import Evidence
from app.models.extraction import ExtractedField
from app.models.mismatch import Mismatch
from app.models.property_field_source import PropertyFieldSource
from app.models.property_profile import PropertyProfile
from app.models.risk_assessment import RiskAssessment
from app.models.risk_factor import RiskFactor
from app.models.user import User
from app.models.validation import ValidationRun
from app.services.case_access_service import CaseAccessService
from app.services.risk.mismatch_engine import MismatchEngine
from app.services.risk.risk_rules import RISK_RULE_VERSION, RiskRules
from app.services.risk.severity_rules import SEVERITY_RULE_VERSION, SeverityRules


class RiskEngine:
    """Deterministic risk calculation service orchestrating discrepancy synthesis, factor weighting, and case review priority classification."""

    @staticmethod
    async def calculate_case_risk(
        db: AsyncSession,
        case_id: uuid.UUID,
        user: Optional[User] = None,
        require_jurisdiction: bool = True,
    ) -> RiskAssessment:
        """Calculate or recalculate deterministic risk score for a case."""
        case_stmt = select(Case).where(Case.id == case_id)
        case_res = await db.execute(case_stmt)
        case = case_res.scalar_one_or_none()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found.",
            )

        if user and require_jurisdiction:
            if user.role == UserRole.CIVILIAN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Civilians cannot trigger risk calculations.",
                )
            await CaseAccessService.verify_case_access(db, user, case)

        # 1. Fetch PropertyProfile with conflicts and field sources
        prof_stmt = (
            select(PropertyProfile)
            .where(PropertyProfile.case_id == case_id)
            .options(
                selectinload(PropertyProfile.conflicts),
                selectinload(PropertyProfile.field_sources),
            )
        )
        prof_res = await db.execute(prof_stmt)
        profile = prof_res.scalar_one_or_none()
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Property profile has not been generated for this case.",
            )

        # 2. Build traceability lookup maps: field_name -> extracted_field_id -> evidence_id
        field_source_map: Dict[str, uuid.UUID] = {}
        for s in profile.field_sources:
            field_source_map[s.field_name] = s.extracted_field_id

        ext_ids = list(field_source_map.values())
        extracted_field_evidence_map: Dict[uuid.UUID, uuid.UUID] = {}
        if ext_ids:
            ev_stmt = select(Evidence).where(Evidence.extracted_field_id.in_(ext_ids))
            ev_res = await db.execute(ev_stmt)
            for ev in ev_res.scalars().all():
                if ev.extracted_field_id:
                    extracted_field_evidence_map[ev.extracted_field_id] = ev.id

        # 3. Load latest database and GIS validation runs
        db_run_stmt = (
            select(ValidationRun)
            .where(
                ValidationRun.property_profile_id == profile.id,
                ValidationRun.validation_type == ValidationType.DATABASE,
            )
            .options(selectinload(ValidationRun.results))
            .order_by(ValidationRun.created_at.desc())
        )
        db_run_res = await db.execute(db_run_stmt)
        db_run = db_run_res.scalars().first()

        gis_run_stmt = (
            select(ValidationRun)
            .where(
                ValidationRun.property_profile_id == profile.id,
                ValidationRun.validation_type == ValidationType.GIS,
            )
            .options(selectinload(ValidationRun.results))
            .order_by(ValidationRun.created_at.desc())
        )
        gis_run_res = await db.execute(gis_run_stmt)
        gis_run = gis_run_res.scalars().first()

        # 4. Generate all discrepancies via MismatchEngine
        all_mismatches: List[Mismatch] = []

        if db_run:
            db_mismatches = MismatchEngine.generate_from_validation_results(
                case_id=case_id,
                profile_id=profile.id,
                val_run=db_run,
                field_source_map=field_source_map,
                extracted_field_evidence_map=extracted_field_evidence_map,
            )
            all_mismatches.extend(db_mismatches)

        if gis_run:
            gis_mismatches = MismatchEngine.generate_from_validation_results(
                case_id=case_id,
                profile_id=profile.id,
                val_run=gis_run,
                field_source_map=field_source_map,
                extracted_field_evidence_map=extracted_field_evidence_map,
            )
            all_mismatches.extend(gis_mismatches)

        if profile.conflicts:
            conflict_mismatches = MismatchEngine.generate_from_extraction_conflicts(
                case_id=case_id,
                profile_id=profile.id,
                conflicts=profile.conflicts,
                field_source_map=field_source_map,
                extracted_field_evidence_map=extracted_field_evidence_map,
            )
            all_mismatches.extend(conflict_mismatches)

        # 5. Persist fresh mismatches for this assessment snapshot
        for m in all_mismatches:
            db.add(m)
        await db.flush()

        # 6. Deduplicate and score risk factors
        seen_factors = set()
        factors_to_create: List[RiskFactor] = []
        raw_score = 0

        for m in all_mismatches:
            dedup_key = (m.mismatch_type, m.field_name)
            if dedup_key in seen_factors:
                continue
            seen_factors.add(dedup_key)

            points = RiskRules.get_points(m.mismatch_type)
            raw_score += points

            factor = RiskFactor(
                id=uuid.uuid4(),
                mismatch_id=m.id,
                factor_code=m.mismatch_type.value.upper(),
                severity=m.severity,
                points=points,
                description=m.description,
            )
            factors_to_create.append(factor)

        # Zero mismatch case
        if not factors_to_create:
            raw_score = 0
            clean_factor = RiskFactor(
                id=uuid.uuid4(),
                mismatch_id=None,
                factor_code="NO_DISCREPANCIES",
                severity=MismatchSeverity.LOW,
                points=0,
                description="No configured discrepancies were detected by completed validation checks.",
            )
            factors_to_create.append(clean_factor)

        risk_score = min(raw_score, 100)
        risk_level = RiskRules.get_risk_level(risk_score)

        # 7. Create immutable RiskAssessment entity
        assessment = RiskAssessment(
            id=uuid.uuid4(),
            case_id=case_id,
            property_profile_id=profile.id,
            property_profile_version=profile.version,
            risk_score=risk_score,
            raw_score=raw_score,
            risk_level=risk_level,
            status=RiskAssessmentStatus.COMPLETED,
            risk_version=RISK_RULE_VERSION,
            severity_rule_version=SEVERITY_RULE_VERSION,
            database_validation_run_id=db_run.id if db_run else None,
            gis_validation_run_id=gis_run.id if gis_run else None,
            calculated_at=datetime.now(timezone.utc),
        )
        db.add(assessment)
        await db.flush()

        for f in factors_to_create:
            f.risk_assessment_id = assessment.id
            db.add(f)

        # Update case risk level
        case.risk_level = risk_level
        await db.commit()

        logger.info(
            "Calculated risk assessment %s for case %s: score=%d (raw=%d), level=%s, %d factors.",
            assessment.id,
            case_id,
            risk_score,
            raw_score,
            risk_level.value,
            len(factors_to_create),
        )

        return await RiskEngine.get_risk_assessment_by_id(db, assessment.id)

    @staticmethod
    async def get_risk_assessment_by_id(
        db: AsyncSession, assessment_id: uuid.UUID
    ) -> RiskAssessment:
        """Fetch risk assessment by ID with factors and mismatches preloaded."""
        stmt = (
            select(RiskAssessment)
            .where(RiskAssessment.id == assessment_id)
            .options(
                selectinload(RiskAssessment.factors).selectinload(RiskFactor.mismatch),
            )
        )
        res = await db.execute(stmt)
        return res.scalar_one()

    @staticmethod
    async def get_current_case_risk(
        db: AsyncSession, case_id: uuid.UUID, user: User
    ) -> RiskAssessment:
        """Get latest completed risk assessment for a case."""
        case_stmt = select(Case).where(Case.id == case_id)
        case_res = await db.execute(case_stmt)
        case = case_res.scalar_one_or_none()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found.",
            )
        await CaseAccessService.verify_case_access(db, user, case)

        stmt = (
            select(RiskAssessment)
            .where(
                RiskAssessment.case_id == case_id,
                RiskAssessment.status == RiskAssessmentStatus.COMPLETED,
            )
            .options(
                selectinload(RiskAssessment.factors).selectinload(RiskFactor.mismatch),
            )
            .order_by(RiskAssessment.calculated_at.desc())
        )
        res = await db.execute(stmt)
        assessment = res.scalars().first()
        if not assessment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Risk assessment has not been calculated for this case.",
            )
        return assessment

    @staticmethod
    async def list_case_risk_history(
        db: AsyncSession, case_id: uuid.UUID, user: User
    ) -> List[RiskAssessment]:
        """List historical risk assessments for a case."""
        case_stmt = select(Case).where(Case.id == case_id)
        case_res = await db.execute(case_stmt)
        case = case_res.scalar_one_or_none()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found.",
            )
        await CaseAccessService.verify_case_access(db, user, case)

        stmt = (
            select(RiskAssessment)
            .where(RiskAssessment.case_id == case_id)
            .options(
                selectinload(RiskAssessment.factors).selectinload(RiskFactor.mismatch),
            )
            .order_by(RiskAssessment.calculated_at.desc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def list_case_mismatches(
        db: AsyncSession,
        case_id: uuid.UUID,
        user: User,
        severity: Optional[MismatchSeverity] = None,
        source: Optional[MismatchSource] = None,
        mismatch_type: Optional[MismatchType] = None,
    ) -> List[Mismatch]:
        """Query and filter discrepancies for a case sorted by severity."""
        case_stmt = select(Case).where(Case.id == case_id)
        case_res = await db.execute(case_stmt)
        case = case_res.scalar_one_or_none()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found.",
            )
        await CaseAccessService.verify_case_access(db, user, case)

        stmt = (
            select(Mismatch)
            .where(Mismatch.case_id == case_id)
            .options(
                selectinload(Mismatch.evidence_links),
            )
        )
        if severity:
            stmt = stmt.where(Mismatch.severity == severity)
        if source:
            stmt = stmt.where(Mismatch.mismatch_source == source)
        if mismatch_type:
            stmt = stmt.where(Mismatch.mismatch_type == mismatch_type)

        stmt = stmt.order_by(
            Mismatch.severity.desc(),
            Mismatch.created_at.desc(),
        )

        res = await db.execute(stmt)
        return list(res.scalars().all())
