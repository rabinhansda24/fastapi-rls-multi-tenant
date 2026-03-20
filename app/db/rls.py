from contextlib import contextmanager
from typing import Generator
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.db.session import SessionLocal

logger = get_logger(__name__)

@contextmanager
def rls_session(tenant_id: UUID, user_id: UUID) -> Generator[Session, None, None]:
    """
    Pool-safe RLS session:
    - starts a transaction
    - sets tenant/user context transaction-locally
    - guarantees no context leaks via connection pooling
    """
    db: Session = SessionLocal()
    try:
        logger.debug("Opening context-managed RLS session tenant_id=%s user_id=%s", tenant_id, user_id)
        with db.begin():
            db.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant_id)})
            db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": str(user_id)})
            yield db
        # commit happens automatically here if no exception
        logger.debug("Committed context-managed RLS session tenant_id=%s user_id=%s", tenant_id, user_id)
    except Exception:
        logger.exception("RLS session failed tenant_id=%s user_id=%s", tenant_id, user_id)
        raise
    finally:
        db.close()
        logger.debug("Closed context-managed RLS session tenant_id=%s user_id=%s", tenant_id, user_id)
