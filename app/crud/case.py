from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.domain.case_enum import CaseEventType, CaseStatus
from app.models.case import Case
from app.models.case_events import CaseEvent
from app.schemas.case import CaseCreate, CaseEventCreate

def create_case(db: Session, *, case_in: CaseCreate, tenant_id: UUID, created_by: UUID) -> Case:
    """
    Create a new case. The tenant_id and created_by are required to ensure that the case is associated with the correct tenant and user.
    """
    try:
        case = Case(
            tenant_id=tenant_id,
            created_by=created_by,
            status=case_in.status
        )
        db.add(case)
        db.commit()
        db.refresh(case)
        return case
    except Exception as e:
        db.rollback()
        raise e
    
def create_case_no_commit(db: Session, *, case_in: CaseCreate, tenant_id: UUID, created_by: UUID) -> Case:
    """
    Create a new case without committing the transaction. This can be useful when you want to create a case and then perform additional operations (like creating related events) before committing.
    The tenant_id and created_by are required to ensure that the case is associated with the correct tenant and user.
    """
    case = Case(
        tenant_id=tenant_id,
        created_by=created_by,
        status=case_in.status
    )
    db.add(case)
    db.flush()  # Flush to assign an ID to the case, but do not commit yet
    return case
    
def get_case(db: Session, *, case_id: UUID) -> Case | None:
    """
    Get a case by its unique ID. This operation should be accessible to users who have permissions to view case information, such as tenant managers and supervisors.
    """
    try:
        stmt = select(Case).where(Case.id == case_id)
        result = db.execute(stmt).scalar_one_or_none()
        return result
    except Exception as e:
        raise e
    
def list_cases(db: Session) -> list[Case]:
    """
    List all cases for a given tenant. This operation should be accessible to users who have permissions to view case information, such as tenant managers and supervisors.
    """
    try:
        stmt = select(Case)
        results = db.execute(stmt).scalars().all()
        return results
    except Exception as e:
        raise e
    

def create_case_event(db: Session, *, event_in: CaseEventCreate, tenant_id: UUID, created_by: UUID) -> CaseEvent:
    """
    Create a new case event. The tenant_id and created_by are required to ensure that the event is associated with the correct tenant and user.
    """
    try:
        event = CaseEvent(
            tenant_id=tenant_id,
            case_id=event_in.case_id,
            actor_id=created_by,
            event_type=event_in.event_type,
            payload=event_in.payload
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event
    except Exception as e:
        db.rollback()
        raise e
    
def create_case_event_no_commit(db: Session, *, event_in: CaseEventCreate, tenant_id: UUID, created_by: UUID) -> CaseEvent:
    """
    Create a new case event without committing the transaction. This can be useful when you want to create an event and then perform additional operations before committing.
    The tenant_id and created_by are required to ensure that the event is associated with the correct tenant and user.
    """
    print("create_case_event_no_commit called")
    try:
        event = CaseEvent(
            tenant_id=tenant_id,
            case_id=event_in.case_id,
            actor_id=created_by,
            event_type=event_in.event_type,
            payload=event_in.payload,
            idempotency_key=event_in.idempotency_key
        )
        print(f"Event object created {event}")
        db.add(event)
        db.flush()  # Flush to assign an ID to the event, but do not commit yet
        print(f"CaseEvent added: {event.id}")
        return event
    except Exception as e:
        db.rollback()
        raise e
    
def get_case_events(db: Session, *, case_id: UUID) -> list[CaseEvent]:
    """
    Get all events for a given case. This operation should be accessible to users who have permissions to view case information, such as tenant managers and supervisors.
    """
    try:
        stmt = select(CaseEvent).where(CaseEvent.case_id == case_id)
        results = db.execute(stmt).scalars().all()
        print(f"Retrieved {len(results)} events for case_id {case_id}")
        return results
    except Exception as e:
        raise e
    
def update_case_status_no_commit(db: Session, *, case: Case, new_status: CaseStatus) -> Case:
    """
    Update the status of a case without committing the transaction. This can be useful when you want to update the case and then perform additional operations (like creating related events) before committing.
    """
    case.status = new_status
    db.add(case)
    db.flush()  # Flush to save changes to the case, but do not commit yet
    return case

def get_case_by_idempotency_key(db: Session, *, case_id: UUID, idempotency_key: str) -> CaseEvent | None:
    """
    Get a case event by its unique ID and idempotency key. This can be useful to ensure that duplicate events are not created when the same request is retried.
    """
    try:
        stmt = select(CaseEvent).where(CaseEvent.case_id == case_id, CaseEvent.idempotency_key == idempotency_key)
        result = db.execute(stmt).scalar_one_or_none()
        return result
    except Exception as e:
        raise e
    
def create_status_change_event_no_commit(
    db: Session,
    *,
    tenant_id: UUID,
    case_id: UUID,
    created_by: UUID,
    old_status: CaseStatus,
    new_status: CaseStatus,
    idempotency_key: str,
    reason: str | None = None
) -> CaseEvent:
    """
    Create a case status change event without committing the transaction. This can be useful when you want to create an event and then perform additional operations before committing.
    The tenant_id and created_by are required to ensure that the event is associated with the correct tenant and user.
    """
    payload = {
        "old_status": old_status.value,
        "new_status": new_status.value,
    }
    if reason:
        payload["reason"] = reason
    event = CaseEvent(
        tenant_id=tenant_id,
        case_id=case_id,
        actor_id=created_by,
        event_type=CaseEventType.STATUS_CHANGED,
        payload=payload,
        idempotency_key=idempotency_key
    )
    db.add(event)
    db.flush()  # Flush to assign an ID to the event, but do not commit yet
    return event

    
