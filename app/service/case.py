import logging
from uuid import UUID
from sqlalchemy.orm import Session
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

from app.crud.case import (
    get_case,
    list_cases,
    get_case_events,
    create_case_no_commit,
    create_case_event_no_commit,
    update_case_status_no_commit,
    get_case_by_idempotency_key,
    create_status_change_event_no_commit,
)
from app.schemas.case import CaseCreate, CaseEventCreate, CaseStatusUpdateRequest, CaseStatusUpdateResponse, CaseResponse
from app.domain.case_enum import CaseEventType, CaseStatus

def create_new_case(db: Session, *, case_in: CaseCreate, tenant_id: UUID, created_by: UUID) -> CaseResponse:
    """
    Create a new case. The tenant_id and created_by are required to ensure that the case is associated with the correct tenant and user.
    """
    try:
        case = create_case_no_commit(db, case_in=case_in, tenant_id=tenant_id, created_by=created_by)
        idempotency_key = f"case_created:{case.id}"
        event_payload: dict = {
            "case_id": str(case.id),
            "status": case.status,
        }
        case_event_in = CaseEventCreate(
            case_id=case.id,
            event_type=CaseEventType.CASE_CREATED,
            payload=event_payload,
            idempotency_key=idempotency_key
        )
        create_case_event_no_commit(db, event_in=case_event_in, tenant_id=tenant_id, created_by=created_by)
        db.commit()
        db.refresh(case)
        return CaseResponse(
            id=case.id,
            tenant_id=case.tenant_id,
            created_by=case.created_by,
            status=case.status,
            created_at=case.created_at
        )
    except Exception as e:
        logger.exception("Failed to create case")
        raise HTTPException(status_code=500, detail="Internal server error")
    
def get_all_cases(db: Session, *, limit: int = 50, offset: int = 0) -> list:
    """
    List all cases for a given tenant with pagination.
    """
    try:
        return list_cases(db, limit=limit, offset=offset)
    except Exception:
        logger.exception("Failed to list cases")
        raise HTTPException(status_code=500, detail="Internal server error")
    
def get_case_by_id(db: Session, *, case_id: UUID):
    """
    Get a case by its unique ID. This operation should be accessible to users who have permissions to view case information, such as tenant managers and supervisors.
    """
    try:
        case = get_case(db, case_id=case_id)
    except Exception:
        logger.exception("Failed to fetch case %s", case_id)
        raise HTTPException(status_code=500, detail="Internal server error")
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case
    
def append_case_event(db: Session, *, event_in: CaseEventCreate, tenant_id: UUID, created_by: UUID):
    """
    Create a new case event. The tenant_id and created_by are required to ensure that the event is associated with the correct tenant and user.
    """
    case = get_case(db, case_id=event_in.case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    try:
        event = create_case_event_no_commit(db, event_in=event_in, tenant_id=tenant_id, created_by=created_by)
        db.commit()
        db.refresh(event)
        return event
    except Exception:
        logger.exception("Failed to append event to case %s", event_in.case_id)
        raise HTTPException(status_code=500, detail="Internal server error")
    
def list_events_for_case(db: Session, *, case_id: UUID):
    """
    List all events for a given case. This operation should be accessible to users who have permissions to view case information, such as tenant managers and supervisors.
    """
    try:
        return get_case_events(db, case_id=case_id)
    except Exception:
        logger.exception("Failed to list events for case %s", case_id)
        raise HTTPException(status_code=500, detail="Internal server error")
    

def update_case_status(db: Session, *, case_id: UUID, tenant_id: UUID, created_by: UUID, request: CaseStatusUpdateRequest) -> CaseStatusUpdateResponse:
    """
    Atomic status update:
    - verifies case exists (RLS enforces tenant isolation)
    - idempotency: if same idempotency_key already used, return existing result
    - updates case.status and appends STATUS_CHANGED event in one transaction
    """
    # first idempotency check: has this idempotency_key already been used for this case?
    existing_event = get_case_by_idempotency_key(db, case_id=case_id, idempotency_key=request.idempotency_key)
    if existing_event:
        # if the event already exists, return the existing status update response
        payload = existing_event.payload or {}
        new_status = payload.get("new_status")
        return CaseStatusUpdateResponse(
            case_id=case_id,
            new_status=CaseStatus(new_status) if new_status else None,
            event_id=existing_event.id,
            event_type=existing_event.event_type
        )
    
    case = get_case(db, case_id=case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    
    old_status = case.status
    if old_status == request.status:
        # still write an event? In regulated systems, usually NO unless you want a heartbeat.
        # We'll treat this as idempotent no-op but still allow client retries via idempotency key.
        pass

    try:
        
        # Re-check idempotency key inside transaction to prevent race conditions
        existing_event = get_case_by_idempotency_key(db, case_id=case_id, idempotency_key=request.idempotency_key)
        if existing_event:
            payload = existing_event.payload or {}
            new_status = payload.get("new_status")
            return CaseStatusUpdateResponse(
                case_id=case_id,
                new_status=CaseStatus(new_status) if new_status else None,
                event_id=existing_event.id,
                event_type=existing_event.event_type
            )
        # Update case status
        update_case_status_no_commit(db, case=case, new_status=request.status)
        # Create status change event
        event = create_status_change_event_no_commit(
            db,
            tenant_id=tenant_id,
            case_id=case_id,
            created_by=created_by,
            old_status=old_status,
            new_status=request.status,
            idempotency_key=request.idempotency_key,
            reason=request.reason
        )
        db.commit()  # Commit the transaction to save both the case update and the event atomically
        return CaseStatusUpdateResponse(
            case_id=case_id,
            new_status=request.status,
            event_id=event.id,
            event_type=event.event_type
        )
    except IntegrityError as e:
        # This can happen if there's a unique constraint violation on the idempotency key, which means another transaction has already created an event with this idempotency key.
        # In that case, we can safely assume that the event was created and return the existing event's details.
        db.rollback()  # Rollback the failed transaction before querying for the existing event
        existing_event = get_case_by_idempotency_key(db, case_id=case_id, idempotency_key=request.idempotency_key)
        if existing_event:
            payload = existing_event.payload or {}
            new_status = payload.get("new_status")
            return CaseStatusUpdateResponse(
                case_id=case_id,
                new_status=CaseStatus(new_status) if new_status else None,
                event_id=existing_event.id,
                event_type=existing_event.event_type
            )
        else:
            logger.error("IntegrityError on idempotency key %s but no existing event found", request.idempotency_key)
            raise HTTPException(status_code=500, detail="Internal server error")
    
