from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID

from app.schemas.tenant import TenantResponse

from app.crud.tenant import get_tenant

from app.db.public import get_db

router = APIRouter(prefix="/tenants", tags=["Tenants"])
    

@router.get("/{tenant_id}", response_model=TenantResponse, summary="Get a tenant by ID", description="Retrieve a tenant by its unique ID.")
async def get_tenant_by_id(tenant_id: UUID, db=Depends(get_db)):
    tenant = get_tenant(db, tenant_id=tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant
    