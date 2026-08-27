from typing import Any, Dict, List, Union
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.audit_service import AuditService

router = APIRouter(tags=["Audit Trail"])


@router.get(
    "/cases/{case_id}/audit",
    response_model=List[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Get Case Audit Trail",
    description="Retrieve chronological audit trail for a case. Civilians receive a simplified milestone timeline, while Officers and Super Admins receive comprehensive audit logs.",
)
async def get_case_audit(
    case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Fetch audit history filtered according to actor permissions."""
    return await AuditService.list_case_audit_events(
        db=db,
        case_id=case_id,
        user=current_user,
    )
