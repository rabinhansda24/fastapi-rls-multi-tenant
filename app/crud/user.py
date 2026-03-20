from sqlalchemy.orm import Session
from sqlalchemy import select
from uuid import UUID

from app.models.user import User
from app.schemas.user import CreateUser, UserResponse, UserFullResponse

def create_user(db: Session, *, user_in: CreateUser, tenant_id: UUID, password_hash: str) -> UserResponse:
    """
    Create a new user. The tenant_id is required to ensure that the user is associated with the correct tenant.
    """
    user = User(
        name=user_in.name,
        email=user_in.email,
        password_hash=password_hash,
        role=user_in.role,
        tenant_id=tenant_id,
    )
    db.add(user)
    db.flush()  # populate id via RETURNING; dependency commits the transaction
    return UserResponse.model_validate(user)
    

def get_user(db: Session, *, user_id: UUID, tenant_id: UUID) -> UserResponse | None:
    """Get a user by ID and tenant ID. This ensures that users can only access their own tenant's data."""
    stmt = select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    result = db.execute(stmt).scalar_one_or_none()
    return UserResponse.model_validate(result) if result else None


def list_users(db: Session, tenant_id: UUID) -> list[UserResponse]:
    """List all users for a given tenant."""
    stmt = select(User).where(User.tenant_id == tenant_id)
    return [UserResponse.model_validate(u) for u in db.execute(stmt).scalars().all()]

def get_user_by_email(db: Session, *, email: str, tenant_id: UUID) -> UserFullResponse | None:
    """Get a user by email and tenant ID for authentication."""
    stmt = select(User).where(User.email == email, User.tenant_id == tenant_id)
    result = db.execute(stmt).scalar_one_or_none()
    return UserFullResponse.model_validate(result) if result else None