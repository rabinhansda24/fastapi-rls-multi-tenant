from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID

from app.core.logging_config import get_logger
from app.schemas.tenant import TenantResponse

from app.crud.tenant import get_tenant

from app.db.public import get_db

router = APIRouter(prefix="/tenants", tags=["Tenants"])
logger = get_logger(__name__)
    

@router.get("/{tenant_id}", response_model=TenantResponse, summary="Get a tenant by ID", description="Retrieve a tenant by its unique ID.")
async def get_tenant_by_id(tenant_id: UUID, db=Depends(get_db)):
    logger.debug("Fetching tenant tenant_id=%s", tenant_id)
    tenant = get_tenant(db, tenant_id=tenant_id)
    if tenant is None:
        logger.warning("Tenant not found tenant_id=%s", tenant_id)
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant
    
