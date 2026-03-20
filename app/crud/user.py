from sqlalchemy.orm import Session
from sqlalchemy import select
from uuid import UUID

from app.core.logging_config import get_logger
from app.models.user import User
from app.schemas.user import CreateUser, UserResponse, UserFullResponse

logger = get_logger(__name__)

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
    logger.info("Created user tenant_id=%s user_id=%s email=%s role=%s", tenant_id, user.id, user.email, user.role)
    return UserResponse.model_validate(user)
    

def get_user(db: Session, *, user_id: UUID, tenant_id: UUID) -> UserResponse | None:
    """Get a user by ID and tenant ID. This ensures that users can only access their own tenant's data."""
    logger.debug("Fetching user tenant_id=%s user_id=%s", tenant_id, user_id)
    stmt = select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    result = db.execute(stmt).scalar_one_or_none()
    return UserResponse.model_validate(result) if result else None


def list_users(db: Session, tenant_id: UUID) -> list[UserResponse]:
    """List all users for a given tenant."""
    logger.debug("Listing users tenant_id=%s", tenant_id)
    stmt = select(User).where(User.tenant_id == tenant_id)
    return [UserResponse.model_validate(u) for u in db.execute(stmt).scalars().all()]

def get_user_by_email(db: Session, *, email: str, tenant_id: UUID) -> UserFullResponse | None:
    """Get a user by email and tenant ID for authentication."""
    logger.debug("Fetching user by email tenant_id=%s email=%s", tenant_id, email)
    stmt = select(User).where(User.email == email, User.tenant_id == tenant_id)
    result = db.execute(stmt).scalar_one_or_none()
    return UserFullResponse.model_validate(result) if result else None
