from pydantic import BaseModel
from uuid import UUID

class CreatePing(BaseModel):
    name: str
    age: int


class PingResponse(BaseModel):
    id: UUID
    name: str
    age: int

    class Config:
        from_attributes = True