from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.schemas.auth import TokenClaims

bearer = HTTPBearer(auto_error=True)
logger = get_logger(__name__)

def get_principal(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
) -> TokenClaims:
    """
    Extracts and validates the JWT from Authorization: Bearer <token>.
    Returns TokenClaims(user_id, tenant_id, ...) on success.
    """
    token = creds.credentials
    try:
        claims = decode_access_token(token)
        logger.debug("Authenticated principal tenant_id=%s user_id=%s", claims.tenant_id, claims.user_id)
        return claims
    except ValueError as e:
        logger.warning("Authentication failed detail=%s", str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_rls_session(principal: TokenClaims = Depends(get_principal)):
    db: Session = SessionLocal()
    try:
        logger.debug("Opening RLS session tenant_id=%s user_id=%s", principal.tenant_id, principal.user_id)
        # true = transaction-local: config is auto-reset on COMMIT/ROLLBACK, pool-safe
        db.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(principal.tenant_id)},
        )
        db.execute(
            text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": str(principal.user_id)},
        )
        yield db
        db.commit()
        logger.debug("Committed RLS session tenant_id=%s user_id=%s", principal.tenant_id, principal.user_id)
    except Exception:
        logger.exception("Rolling back RLS session tenant_id=%s user_id=%s", principal.tenant_id, principal.user_id)
        db.rollback()
        raise
    finally:
        db.close()
        logger.debug("Closed RLS session tenant_id=%s user_id=%s", principal.tenant_id, principal.user_id)
