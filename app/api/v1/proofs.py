from typing import List, Optional
import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.proof import (
    ProofCancelRequest,
    ProofRejectRequest,
    ProofRequestCreate,
    ProofRequestHistoryResponse,
    ProofRequestResponse,
    ProofSubmissionResponse,
)
from app.services.proof_request_service import ProofRequestService

router = APIRouter(tags=["Proof Request + Civilian Response Workflow"])


@router.post(
    "/cases/{case_id}/proof-requests",
    response_model=ProofRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Evidentiary Proof Request",
    description="Issue a formal supplementary evidence request to the civilian case owner (Area Officer or Super Admin only).",
)
async def create_case_proof_request(
    case_id: uuid.UUID,
    payload: ProofRequestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProofRequestResponse:
    """Create a new proof request for a case."""
    proof_request = await ProofRequestService.create_proof_request(
        db=db,
        case_id=case_id,
        payload=payload,
        user=current_user,
    )
    return ProofRequestResponse.model_validate(proof_request)


@router.get(
    "/cases/{case_id}/proof-requests",
    response_model=List[ProofRequestResponse],
    status_code=status.HTTP_200_OK,
    summary="List Case Proof Requests",
    description="Retrieve all proof requests associated with a case (Civilian owner, assigned Area Officer, or Super Admin).",
)
async def list_case_proof_requests(
    case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ProofRequestResponse]:
    """List proof requests for a case."""
    requests = await ProofRequestService.list_case_proof_requests(
        db=db,
        case_id=case_id,
        user=current_user,
    )
    return [ProofRequestResponse.model_validate(r) for r in requests]


@router.get(
    "/proof-requests/{proof_request_id}",
    response_model=ProofRequestResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Proof Request Details",
    description="Retrieve specific proof request instructions and submission records.",
)
async def get_proof_request_detail(
    proof_request_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProofRequestResponse:
    """Get single proof request details."""
    proof_request = await ProofRequestService.get_proof_request(
        db=db,
        proof_request_id=proof_request_id,
        user=current_user,
    )
    return ProofRequestResponse.model_validate(proof_request)


@router.post(
    "/proof-requests/{proof_request_id}/submissions",
    response_model=ProofSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Proof Document",
    description="Upload evidentiary file responding to an open proof request (Civilian case owner only).",
)
async def submit_proof_document(
    proof_request_id: uuid.UUID,
    file: UploadFile = File(..., description="Document file to upload (PDF, JPEG, PNG)"),
    comment: Optional[str] = Form(None, max_length=5000, description="Optional civilian remarks"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProofSubmissionResponse:
    """Submit proof document answering request."""
    if current_user.role != UserRole.CIVILIAN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the requested civilian case owner can submit proof.",
        )

    submission = await ProofRequestService.submit_proof(
        db=db,
        proof_request_id=proof_request_id,
        file=file,
        comment=comment,
        user=current_user,
    )
    return ProofSubmissionResponse.model_validate(submission)


@router.post(
    "/proof-requests/{proof_request_id}/accept",
    response_model=ProofRequestResponse,
    status_code=status.HTTP_200_OK,
    summary="Accept Submitted Proof",
    description="Mark a submitted proof request as accepted by the reviewing Area Officer.",
)
async def accept_proof_request(
    proof_request_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProofRequestResponse:
    """Accept proof request."""
    proof_request = await ProofRequestService.accept_proof_request(
        db=db,
        proof_request_id=proof_request_id,
        user=current_user,
    )
    return ProofRequestResponse.model_validate(proof_request)


@router.post(
    "/proof-requests/{proof_request_id}/reject",
    response_model=ProofRequestResponse,
    status_code=status.HTTP_200_OK,
    summary="Reject Submitted Proof",
    description="Reject a submitted proof request with a mandatory factual reason (Area Officer / Admin).",
)
async def reject_proof_request(
    proof_request_id: uuid.UUID,
    payload: ProofRejectRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProofRequestResponse:
    """Reject proof request."""
    proof_request = await ProofRequestService.reject_proof_request(
        db=db,
        proof_request_id=proof_request_id,
        payload=payload,
        user=current_user,
    )
    return ProofRequestResponse.model_validate(proof_request)


@router.post(
    "/proof-requests/{proof_request_id}/cancel",
    response_model=ProofRequestResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel Proof Request",
    description="Cancel an active proof request with explanation (Area Officer / Admin).",
)
async def cancel_proof_request(
    proof_request_id: uuid.UUID,
    payload: ProofCancelRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProofRequestResponse:
    """Cancel proof request."""
    proof_request = await ProofRequestService.cancel_proof_request(
        db=db,
        proof_request_id=proof_request_id,
        payload=payload,
        user=current_user,
    )
    return ProofRequestResponse.model_validate(proof_request)


@router.get(
    "/proof-requests/{proof_request_id}/history",
    response_model=List[ProofRequestHistoryResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Proof Request Audit Trail",
    description="Retrieve chronological audit log history entries for a proof request.",
)
async def get_proof_request_history(
    proof_request_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ProofRequestHistoryResponse]:
    """Retrieve audit history entries for a proof request."""
    history = await ProofRequestService.get_proof_request_history(
        db=db,
        proof_request_id=proof_request_id,
        user=current_user,
    )
    return [ProofRequestHistoryResponse.model_validate(h) for h in history]
