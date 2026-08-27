from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.enums import (
    MismatchSeverity,
    MismatchSource,
    MismatchType,
    UserRole,
)
from app.models.user import User
from app.schemas.risk import (
    MismatchResponse,
    RiskAssessmentResponse,
)
from app.services.risk.risk_engine import RiskEngine

router = APIRouter(tags=["Discrepancies & Risk Assessment"])


@router.post(
    "/cases/{case_id}/risk-assessment",
    response_model=RiskAssessmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Calculate Case Risk Assessment",
    description="Trigger deterministic, evidence-linked risk scoring and review priority calculation (Area Officer or Super Admin only).",
)
async def calculate_case_risk(
    case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RiskAssessmentResponse:
    """Calculate and persist an immutable risk assessment snapshot for a case."""
    assessment = await RiskEngine.calculate_case_risk(
        db=db,
        case_id=case_id,
        user=current_user,
        require_jurisdiction=True,
    )
    return RiskAssessmentResponse.model_validate(assessment)


@router.get(
    "/cases/{case_id}/risk-assessment/current",
    response_model=RiskAssessmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Current Risk Assessment",
    description="Retrieve the latest completed risk assessment and explainable factor breakdown for a case.",
)
async def get_current_risk_assessment(
    case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RiskAssessmentResponse:
    """Get active risk assessment for a case."""
    assessment = await RiskEngine.get_current_case_risk(
        db=db,
        case_id=case_id,
        user=current_user,
    )
    return RiskAssessmentResponse.model_validate(assessment)


@router.get(
    "/cases/{case_id}/risk-assessments",
    response_model=List[RiskAssessmentResponse],
    status_code=status.HTTP_200_OK,
    summary="List Case Risk History",
    description="Retrieve chronological historical risk assessments for a case.",
)
async def list_case_risk_history(
    case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[RiskAssessmentResponse]:
    """List historical risk assessments for a case."""
    assessments = await RiskEngine.list_case_risk_history(
        db=db,
        case_id=case_id,
        user=current_user,
    )
    return [RiskAssessmentResponse.model_validate(a) for a in assessments]


@router.get(
    "/cases/{case_id}/mismatches",
    response_model=List[MismatchResponse],
    status_code=status.HTTP_200_OK,
    summary="List Case Mismatches",
    description="Query detected discrepancies with evidence references, filtered by severity, source, or type.",
)
async def list_case_mismatches(
    case_id: uuid.UUID,
    severity: Optional[MismatchSeverity] = Query(None, description="Filter by severity tier ('low', 'medium', 'high', 'critical')"),
    source: Optional[MismatchSource] = Query(None, description="Filter by discrepancy origin ('database', 'gis', 'extraction')"),
    mismatch_type: Optional[MismatchType] = Query(None, description="Filter by canonical mismatch type"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[MismatchResponse]:
    """Retrieve filtered discrepancies for authorized case reviewer."""
    mismatches = await RiskEngine.list_case_mismatches(
        db=db,
        case_id=case_id,
        user=current_user,
        severity=severity,
        source=source,
        mismatch_type=mismatch_type,
    )
    return [MismatchResponse.model_validate(m) for m in mismatches]
