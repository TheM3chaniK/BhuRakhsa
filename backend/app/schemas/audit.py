from datetime import datetime
from typing import Any, Dict, List, Optional, Union
import uuid
from pydantic import BaseModel, ConfigDict

from app.models.enums import AuditAction, AuditActorType


class AuditEventResponse(BaseModel):
    """Detailed audit log item for Area Officers and Super Admins."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: Optional[uuid.UUID] = None
    actor_id: Optional[uuid.UUID] = None
    actor_type: str
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[uuid.UUID] = None
    old_state: Optional[str] = None
    new_state: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime


class CivilianAuditTimelineItem(BaseModel):
    """Simplified, safe chronological audit timeline item for civilians."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: Optional[uuid.UUID] = None
    action: str
    title: str
    status: Optional[str] = None
    created_at: datetime
