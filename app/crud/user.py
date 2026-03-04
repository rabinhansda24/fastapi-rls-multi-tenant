from sqlalchemy.orm import Session
from sqlalchemy import select
from uuid import UUID

from app.models.user import User
from app.schemas.user import CreateUser, UserResponse, UserFullResponse

def create_user(db: Session, *, user_in: CreateUser, tenant_id: UUID, password_hash: str) -> UserResponse:
    """
    Create a new user. The tenant_id is required to ensure that the user is associated with the correct tenant.
    """
    try:
        user = User(
            name=user_in.name,
            email=user_in.email,
            password_hash=password_hash,
            role=user_in.role,
            tenant_id=tenant_id
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return UserResponse.model_validate(user)
    except Exception as e:
        db.rollback()
        raise e
    

def get_user(db: Session, *, user_id: UUID, tenant_id: UUID) -> UserResponse | None:
    """Get a user by ID and tenant ID. This ensures that users can only access their own tenant's data."""
    try:
        stmt = select(User).where(User.id == user_id, User.tenant_id == tenant_id)
        result = db.execute(stmt).scalar_one_or_none()
        if result is None:
            return None
        return UserResponse.model_validate(result)
    except Exception as e:
        raise e
    

def list_users(db: Session, tenant_id: UUID) -> list[UserResponse]:
    """
    List all users for a given tenant.
    """
    try:
        stmt = select(User).where(User.tenant_id == tenant_id)
        results = db.execute(stmt).scalars().all()
        return [UserResponse.model_validate(user) for user in results]
    except Exception as e:
        raise e
    
def get_user_by_email(db: Session, *, email: str, tenant_id: UUID) -> UserFullResponse | None:
    """
    Get a user by email and tenant ID. This can be useful for authentication and user management operations.
    """
    try:
        stmt = select(User).where(User.email == email, User.tenant_id == tenant_id)
        result = db.execute(stmt).scalar_one_or_none()
        if result is None:
            return None
        return UserFullResponse.model_validate(result)
    except Exception as e:
        raise e