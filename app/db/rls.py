from contextlib import contextmanager
from typing import Generator
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal


@contextmanager
def rls_session(tenant_id: UUID, user_id: UUID) -> Generator[Session, None, None]:
    """
    RLS-safe session:
    - starts a transaction
    - sets the RLS context for the current tenant and user using SET LOCAL (transaction-scoped)
    - garantees context does not leak through connection pooling
    """
    db: Session = SessionLocal()
    try:
        with db.begin():
            db.execute(text("SET LOCAL rls.tenant_id = :tenant_id"), {"tenant_id": str(tenant_id)})
            db.execute(text("SET LOCAL rls.user_id = :user_id"), {"user_id": str(user_id)})
            yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()