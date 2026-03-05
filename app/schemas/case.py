from datetime import datetime
from uuid import UUID
from typing import Any, Optional, Dict

from pydantic import BaseModel, Field

from app.domain.case_enum import CaseStatus, CaseEventType


class CaseCreate(BaseModel):
    status: CaseStatus = CaseStatus.OPEN


class CaseResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    created_by: UUID
    status: CaseStatus
    created_at: datetime

    class Config:
        from_attributes = True


class CaseEventCreate(BaseModel):
    case_id: UUID
    event_type: CaseEventType
    payload: Dict[str, Any] = {}
    idempotency_key: str


class CaseEventResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    case_id: UUID
    actor_id: UUID
    event_type: CaseEventType
    event_ts: datetime
    payload: Dict

    class Config:
        from_attributes = True

class CaseStatusUpdateRequest(BaseModel):
    status: CaseStatus
    idempotency_key: str
    reason: Optional[str] = Field(None, description="Reason for status update, required if status is APPROVED or REJECTED", max_length=500)

class CaseStatusUpdateResponse(BaseModel):
    case_id: UUID
    new_status: CaseStatus
    event_id: UUID
    event_type: CaseEventType