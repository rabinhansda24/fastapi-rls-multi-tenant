from datetime import datetime
from uuid import UUID as PyUUID, uuid4

from sqlalchemy import ForeignKey, String, func, Enum, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.domain.case_enum import CaseEventType

class CaseEvent(Base):
    __tablename__ = "case_events"

    id: Mapped[PyUUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[PyUUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True)
    tenant_id: Mapped[PyUUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    actor_id: Mapped[PyUUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    event_ts: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    event_type: Mapped[CaseEventType] = mapped_column(Enum(CaseEventType, name="case_event_type"), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False)

    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "case_id", "idempotency_key", name="uq_case_event_idempotency"),
    )

    # Relationships
    case = relationship("Case", back_populates="events", lazy="joined")