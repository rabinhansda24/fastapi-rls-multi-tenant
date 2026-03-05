from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from app.schemas.case import CaseCreate, CaseEventCreate, CaseResponse, CaseEventResponse, CaseStatusUpdateRequest, CaseStatusUpdateResponse
from app.service.case import create_new_case, get_all_cases, get_case_by_id, append_case_event, list_events_for_case, update_case_status, update_case_status_no_commit, get_case_by_idempotency_key, create_status_change_event_no_commit

from app.deps.auth import get_rls_session, get_principal

router = APIRouter(prefix="/cases", tags=["Cases"])

@router.post("/", response_model=CaseResponse, summary="Create a new case", description="Create a new case with the provided status.")
async def create_case(case_in: CaseCreate, db=Depends(get_rls_session), principal=Depends(get_principal)):
    """
    Create a new case with the provided status.
    - **status**: Status of the case (e.g., open, closed, pending)
    """
    return create_new_case(db, case_in=case_in, tenant_id=principal.tenant_id, created_by=principal.user_id)

@router.get("/", response_model=List[CaseResponse], summary="List all cases", description="List all cases for the current tenant.")
async def list_cases(db=Depends(get_rls_session)):
    """
    List all cases for the current tenant.
    """
    return get_all_cases(db)

@router.get("/{case_id}", response_model=CaseResponse, summary="Get case by ID", description="Get a case by its unique ID.")
async def get_case(case_id: UUID, db=Depends(get_rls_session)):
    """
    Get a case by its unique ID.
    - **case_id**: The unique ID of the case to retrieve.
    """
    return get_case_by_id(db, case_id=case_id)

@router.post("/events", response_model=CaseEventResponse, summary="Append an event to a case", description="Append a new event to an existing case.")
async def add_case_event(event_in: CaseEventCreate, db=Depends(get_rls_session), principal=Depends(get_principal)):
    """
    Append a new event to an existing case.
    - **case_id**: The unique ID of the case to which the event will be appended.
    - **event_type**: The type of the event (e.g., status_change, comment_added).
    - **details**: Additional details about the event in JSON format.
    """
    return append_case_event(db, event_in=event_in, tenant_id=principal.tenant_id, created_by=principal.user_id)

@router.get("/{case_id}/events", response_model=List[CaseEventResponse], summary="List events for a case", description="List all events associated with a specific case.")
async def list_case_events(case_id: UUID, db=Depends(get_rls_session)):
    """
    List all events associated with a specific case.
    - **case_id**: The unique ID of the case for which to list events.
    """
    return list_events_for_case(db, case_id=case_id)

@router.patch("/{case_id}/status", response_model=CaseStatusUpdateResponse, summary="Update case status", description="Update the status of a case.")
async def update_case_status_request(case_id: UUID, status_update: CaseStatusUpdateRequest, db=Depends(get_rls_session), principal=Depends(get_principal)):
    """
    Update the status of a case.
    - **case_id**: The unique ID of the case to update.
    - **status**: The new status for the case (e.g., open, closed, pending).
    - **idempotency_key**: A unique key to ensure idempotency of the status update operation.
    - **reason**: Optional reason for the status update, required if the new status is APPROVED or REJECTED.
    """
    return update_case_status(db, case_id=case_id, tenant_id=principal.tenant_id, created_by=principal.user_id, request=status_update)