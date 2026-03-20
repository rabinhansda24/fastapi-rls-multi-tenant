from app.db.session import SessionLocal
from app.core.logging_config import get_logger

logger = get_logger(__name__)

def get_db():
    db = SessionLocal()
    try:
        logger.debug("Opening public DB session")
        yield db
        db.commit()
        logger.debug("Committed public DB session")
    except Exception:
        logger.exception("Rolling back public DB session")
        db.rollback()
        raise
    finally:
        db.close()
        logger.debug("Closed public DB session")
