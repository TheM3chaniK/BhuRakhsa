import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.final_decision import CivilianCaseStatusResponse
from app.services.case_access_service import CaseAccessService
from app.services.case_service import CaseService

router = APIRouter(prefix="/me/cases", tags=["Civilian Case Status"])


@router.get(
    "/{case_id}/status",
    response_model=CivilianCaseStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Civilian Case Status",
    description="Retrieve simplified case status for authenticated applicant.",
)
async def get_my_case_status(
    case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CivilianCaseStatusResponse:
    """Retrieve simplified case status view for civilian owner."""
    case = await CaseService.get_case(db, case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found.",
        )
    await CaseAccessService.verify_case_access(db, current_user, case)
    return CivilianCaseStatusResponse(
        case_id=case.id,
        status=case.status,
        updated_at=case.updated_at,
        title=case.title,
    )
