from pydantic import BaseModel
from uuid import UUID

class TokenClaims(BaseModel):
    tenant_id: UUID
    user_id: UUID


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(TokenResponse):
    pass

class TenantRegistrationRequest(BaseModel):
    name: str
    admin_name: str
    admin_email: str
    admin_password: str

class TenantRegistrationResponse(TokenResponse):
    tenant_id: UUID


    