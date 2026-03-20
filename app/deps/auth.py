from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.schemas.auth import TokenClaims

bearer = HTTPBearer(auto_error=True)

def get_principal(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
) -> TokenClaims:
    """
    Extracts and validates the JWT from Authorization: Bearer <token>.
    Returns TokenClaims(user_id, tenant_id, ...) on success.
    """
    token = creds.credentials
    try:
        return decode_access_token(token)
    except ValueError as e:
        # ValueError is what your decode_access_token should raise for invalid/expired tokens
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_rls_session(principal: TokenClaims = Depends(get_principal)):
    db: Session = SessionLocal()
    try:
        # set tenant context for this connection
        db.execute(
            text("SELECT set_config('app.tenant_id', :tid, false)"),
            {"tid": str(principal.tenant_id)},
        )

        db.execute(
            text("SELECT set_config('app.user_id', :uid, false)"),
            {"uid": str(principal.user_id)},
        )

        yield db

    finally:
        db.close()

