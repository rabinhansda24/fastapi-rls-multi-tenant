from pydantic import BaseModel, EmailStr, Field
from uuid import UUID

from app.domain.roles import UserRole


class CreateUser(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    password: str = Field(min_length=8)
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

