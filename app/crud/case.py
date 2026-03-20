from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.logging_config import get_logger

logger = get_logger(__name__)

from app.domain.case_enum import CaseEventType, CaseStatus
from app.models.case import Case
from app.models.case_events import CaseEvent
from app.schemas.case import CaseCreate, CaseEventCreate

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
    logger.info("Created case case_id=%s tenant_id=%s created_by=%s status=%s", case.id, tenant_id, created_by, case.status)
    return case
    
def get_case(db: Session, *, case_id: UUID) -> Case | None:
    logger.debug("Fetching case case_id=%s", case_id)
    stmt = select(Case).where(Case.id == case_id)
    return db.execute(stmt).scalar_one_or_none()

def list_cases(db: Session, *, limit: int = 50, offset: int = 0) -> list[Case]:
    logger.debug("Listing cases limit=%s offset=%s", limit, offset)
    stmt = select(Case).limit(limit).offset(offset)
    return db.execute(stmt).scalars().all()
    

def create_case_event_no_commit(db: Session, *, event_in: CaseEventCreate, tenant_id: UUID, created_by: UUID) -> CaseEvent:
    """
    Create a new case event without committing the transaction.
    """
    event = CaseEvent(
        tenant_id=tenant_id,
        case_id=event_in.case_id,
        actor_id=created_by,
        event_type=event_in.event_type,
        payload=event_in.payload,
        idempotency_key=event_in.idempotency_key,
    )
    db.add(event)
    db.flush()
    logger.info("Created case event event_id=%s case_id=%s event_type=%s", event.id, event.case_id, event.event_type)
    return event
    
def get_case_events(db: Session, *, case_id: UUID) -> list[CaseEvent]:
    logger.debug("Fetching case events case_id=%s", case_id)
    stmt = select(CaseEvent).where(CaseEvent.case_id == case_id).order_by(CaseEvent.event_ts)
    return db.execute(stmt).scalars().all()
    
def update_case_status_no_commit(db: Session, *, case: Case, new_status: CaseStatus) -> Case:
    """
    Update the status of a case without committing the transaction. This can be useful when you want to update the case and then perform additional operations (like creating related events) before committing.
    """
    case.status = new_status
    db.add(case)
    db.flush()  # Flush to save changes to the case, but do not commit yet
    logger.info("Updated case status case_id=%s new_status=%s", case.id, new_status)
    return case

def get_case_by_idempotency_key(db: Session, *, case_id: UUID, idempotency_key: str) -> CaseEvent | None:
    logger.debug("Fetching case event by idempotency key case_id=%s idempotency_key=%s", case_id, idempotency_key)
    stmt = select(CaseEvent).where(CaseEvent.case_id == case_id, CaseEvent.idempotency_key == idempotency_key)
    return db.execute(stmt).scalar_one_or_none()
    
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
    logger.info("Created status change event event_id=%s case_id=%s old_status=%s new_status=%s", event.id, case_id, old_status, new_status)
    return event

    
