from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.enums import (
    CaseStatus,
    ReviewStatus,
    RiskLevel,
    UserRole,
)
from app.models.user import User
from app.schemas.review import (
    CaseReviewResponse,
    DecisionResponse,
    ReviewDetailResponse,
    ReviewHistoryResponse,
    ReviewQueueResponse,
    StartReviewResponse,
    SubmitDecisionRequest,
)
from app.services.review_service import ReviewService

router = APIRouter(tags=["Area Officer Review Workflow"])


@router.get(
    "/officer/reviews/queue",
    response_model=ReviewQueueResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Area Officer Review Queue",
    description="Retrieve review-ready cases within the requesting officer's assigned jurisdiction, prioritized by risk severity.",
)
async def get_officer_review_queue(
    risk_level: Optional[RiskLevel] = Query(None, description="Filter by risk tier ('critical', 'high', 'medium', 'low')"),
    case_status: Optional[CaseStatus] = Query(None, description="Filter by case lifecycle status"),
    review_status: Optional[ReviewStatus] = Query(None, description="Filter by review progress ('not_started', 'in_progress')"),
    limit: int = Query(50, ge=1, le=100, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewQueueResponse:
    """Retrieve filtered review queue for authorized area officer."""
    if current_user.role == UserRole.CIVILIAN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Civilians do not have access to the review queue.",
        )

    return await ReviewService.get_review_queue(
        db=db,
        user=current_user,
        risk_level=risk_level,
        case_status=case_status,
        review_status=review_status,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/cases/{case_id}/review/start",
    response_model=StartReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Start Case Verification Review",
    description="Acquire review lock on a case, mark review in progress, and record audit log entry (Area Officer or Super Admin only).",
)
async def start_case_review(
    case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StartReviewResponse:
    """Start reviewing a case session."""
    if current_user.role == UserRole.CIVILIAN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Civilians cannot review cases.",
        )

    review = await ReviewService.start_review(
        db=db,
        case_id=case_id,
        user=current_user,
    )
    return StartReviewResponse(
        review=CaseReviewResponse.model_validate(review),
        message="Case review started and assigned successfully.",
    )


@router.get(
    "/cases/{case_id}/review",
    response_model=ReviewDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Holistic Case Review Context",
    description="Retrieve complete review package containing case metadata, property profile, documents, validations, mismatches, and risk breakdown.",
)
async def get_case_review_context(
    case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewDetailResponse:
    """Assemble all evidence and analysis for case review screen."""
    context = await ReviewService.get_review_context(
        db=db,
        case_id=case_id,
        user=current_user,
    )
    return ReviewDetailResponse(**context)


@router.post(
    "/cases/{case_id}/review/decision",
    response_model=DecisionResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit Reviewer Decision",
    description="Submit final officer determination (APPROVE / REJECT / REQUEST_PROOF) with mandatory justification rationale and audit snapshot.",
)
async def submit_case_decision(
    case_id: uuid.UUID,
    payload: SubmitDecisionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DecisionResponse:
    """Submit final reviewer decision for case."""
    if current_user.role == UserRole.CIVILIAN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Civilians cannot submit review decisions.",
        )

    review, case_status = await ReviewService.submit_decision(
        db=db,
        case_id=case_id,
        payload=payload,
        user=current_user,
    )
    return DecisionResponse(
        review=CaseReviewResponse.model_validate(review),
        case_status=case_status,
        message=f"Case determination '{payload.decision.value}' recorded successfully.",
    )


@router.get(
    "/cases/{case_id}/review/history",
    response_model=List[ReviewHistoryResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Case Review Audit Trail",
    description="Retrieve immutable chronological audit logs for case review actions and officer transitions.",
)
async def get_case_review_history(
    case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ReviewHistoryResponse]:
    """Retrieve audit history entries for a case."""
    history = await ReviewService.get_review_history(
        db=db,
        case_id=case_id,
        user=current_user,
    )
    return [ReviewHistoryResponse.model_validate(h) for h in history]
