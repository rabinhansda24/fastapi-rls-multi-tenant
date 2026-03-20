from sqlalchemy.orm import Session
from sqlalchemy import select
from uuid import UUID

from app.core.logging_config import get_logger
from app.models.ping import Ping
from app.schemas.ping import CreatePing, PingResponse

logger = get_logger(__name__)

def create_ping(db: Session, *, ping_in: CreatePing) -> PingResponse:
    ping = Ping(name=ping_in.name, age=ping_in.age)
    db.add(ping)
    db.flush()  # dependency commits the transaction
    logger.info("Created ping ping_id=%s name=%s", ping.id, ping.name)
    return PingResponse.model_validate(ping)


def get_ping(db: Session, *, ping_id: UUID) -> PingResponse | None:
    logger.debug("Fetching ping ping_id=%s", ping_id)
    stmt = select(Ping).where(Ping.id == ping_id)
    result = db.execute(stmt).scalar_one_or_none()
    if result is None:
        return None
    return PingResponse.model_validate(result)


def list_pings(db: Session) -> list[PingResponse]:
    logger.debug("Listing pings")
    stmt = select(Ping)
    results = db.execute(stmt).scalars().all()
    return [PingResponse.model_validate(ping) for ping in results]
