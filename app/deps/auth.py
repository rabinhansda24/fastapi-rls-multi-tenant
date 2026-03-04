from fastapi import Depends, HTTPException, Header, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.public import get_db
from app.db.session import SessionLocal
from app.models.user import User
from app.schemas.auth import TokenClaims
from app.schemas.user import CurrentUser

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
        with db.begin():
            db.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(principal.tenant_id)})
            db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": str(principal.user_id)})
            yield db
    finally:
        db.close()

def get_current_user(token: str = Header(...), db=Depends(get_db)) -> CurrentUser:
    """
    Get the current authenticated user based on the provided access token.
    - **token**: Access token provided in the Authorization header"""
    try:
        claims = decode_access_token(token)
        user = db.scalar(
            db.select(User).where(User.id == claims["user_id"], User.tenant_id == claims["tenant_id"])
        )
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")
        return CurrentUser(**user.model_dump())
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")