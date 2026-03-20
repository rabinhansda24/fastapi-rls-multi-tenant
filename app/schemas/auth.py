from pydantic import BaseModel, EmailStr, Field
from uuid import UUID

class TokenClaims(BaseModel):
    tenant_id: UUID
    user_id: UUID


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginResponse(TokenResponse):
    pass

class TenantRegistrationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    admin_name: str = Field(min_length=1)
    admin_email: EmailStr
    admin_password: str = Field(min_length=8)

class TenantRegistrationResponse(TokenResponse):
    tenant_id: UUID


    