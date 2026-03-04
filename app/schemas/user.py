from pydantic import BaseModel, EmailStr
from uuid import UUID

from app.domain.roles import UserRole


class CreateUser(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: UserRole

class UserFullResponse(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    role: UserRole
    tenant_id: UUID
    password_hash: str

    class Config:
        from_attributes = True

class UserResponse(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    role: UserRole
    tenant_id: UUID

    class Config:
        from_attributes = True

class CurrentUser(UserResponse):
    pass