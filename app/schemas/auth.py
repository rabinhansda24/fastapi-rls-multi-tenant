from pydantic import BaseModel
from uuid import UUID

class TokenClaims(BaseModel):
    tenant_id: UUID
    user_id: UUID


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"