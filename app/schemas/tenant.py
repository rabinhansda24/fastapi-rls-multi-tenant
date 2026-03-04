from pydantic import BaseModel
from uuid import UUID

class CreateTenant(BaseModel):
    name: str
    slug: str


class TenantResponse(BaseModel):
    id: UUID
    name: str
    slug: str

    class Config:
        from_attributes = True