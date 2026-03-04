from sqlalchemy.orm import Session
from sqlalchemy import select
from uuid import UUID

from app.models.ping import Ping
from app.schemas.ping import CreatePing, PingResponse


def create_ping(db: Session, *, ping_in: CreatePing) -> PingResponse:
    ping = Ping(name=ping_in.name, age=ping_in.age)
    db.add(ping)
    db.commit()
    db.refresh(ping)
    return PingResponse.model_validate(ping)


def get_ping(db: Session, *, ping_id: UUID) -> PingResponse | None:
    stmt = select(Ping).where(Ping.id == ping_id)
    result = db.execute(stmt).scalar_one_or_none()
    if result is None:
        return None
    return PingResponse.model_validate(result)


def list_pings(db: Session) -> list[PingResponse]:
    stmt = select(Ping)
    results = db.execute(stmt).scalars().all()
    return [PingResponse.model_validate(ping) for ping in results]