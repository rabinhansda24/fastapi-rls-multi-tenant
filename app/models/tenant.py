from sqlalchemy import String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from uuid import UUID as PyUUID, uuid4
from datetime import datetime

from app.models.base import Base

class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[PyUUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, index=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)


    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    