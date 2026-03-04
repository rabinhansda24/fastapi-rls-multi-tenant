from fastapi import APIRouter, Depends, HTTPException


from app.schemas.user import CreateUser, UserResponse
from app.crud.user import create_user

from app.deps.auth import get_rls_session, get_current_user


router = APIRouter(prefix="/users", tags=["Users"])

@router.post("/", response_model=UserResponse, summary="Create a new user", description="Create a new user with the provided name, email, password, role, and tenant ID.")
async def create_new_user(user_in: CreateUser, db=Depends(get_rls_session), current_user=Depends(get_current_user)):
    """
    Create a new user with the provided name, email, password, role.
    - **name**: Name of the user
    - **email**: Email of the user
    - **password**: Password for the user
    - **role**: Role of the user (e.g., admin, user, manager, supervisor)
    """
    try:
        return create_user(db, user_in=user_in, tenant_id=current_user.tenant_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))