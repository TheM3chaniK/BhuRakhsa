from typing import Optional
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.final_decision import FinalDecisionResponse
from app.services.final_decision_service import FinalDecisionService

router = APIRouter(tags=["Final Determination"])


@router.get(
    "/cases/{case_id}/final-decision",
    response_model=FinalDecisionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Case Final Decision Snapshot",
    description="Retrieve the immutable final decision snapshot, including the deterministic risk and validation state at decision time.",
)
async def get_final_decision(
    case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FinalDecisionResponse:
    """Retrieve immutable final decision snapshot for an authorized case."""
    decision = await FinalDecisionService.get_final_decision(
        db=db,
        case_id=case_id,
        user=current_user,
    )
    return FinalDecisionResponse.model_validate(decision)
