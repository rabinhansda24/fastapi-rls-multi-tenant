from fastapi import APIRouter, Depends, HTTPException

from app.core.logging_config import get_logger
from app.core.security import hash_password
from app.schemas.user import CreateUser, UserResponse
from app.crud.user import create_user
from app.deps.auth import get_rls_session, get_principal


router = APIRouter(prefix="/users", tags=["Users"])
logger = get_logger(__name__)

@router.post("/", response_model=UserResponse, summary="Create a new user", description="Create a new user with the provided name, email, password, role, and tenant ID.")
async def create_new_user(user_in: CreateUser, db=Depends(get_rls_session), principal=Depends(get_principal)):
    """
    Create a new user with the provided name, email, password, role.
    - **name**: Name of the user
    - **email**: Email of the user
    - **password**: Password for the user
    - **role**: Role of the user (e.g., admin, user, manager, supervisor)
    """
    try:
        logger.info(
            "Creating user tenant_id=%s email=%s role=%s requested_by=%s",
            principal.tenant_id,
            user_in.email,
            user_in.role,
            principal.user_id,
        )
        return create_user(db, user_in=user_in, tenant_id=principal.tenant_id, password_hash=hash_password(user_in.password))
    except Exception as e:
        logger.exception("Failed to create user tenant_id=%s email=%s", principal.tenant_id, user_in.email)
        raise HTTPException(status_code=400, detail=str(e))
