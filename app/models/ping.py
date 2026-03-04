from sqlalchemy.orm import Mapped, mapped_column
from uuid import UUID as PyUUID, uuid4
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.models.base import Base

class Ping(Base):
    __tablename__ = "ping"

    id: Mapped[PyUUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, index=True, default=uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    age: Mapped[int] = mapped_column(nullable=False)


