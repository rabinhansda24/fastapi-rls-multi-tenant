from sqlalchemy.orm import Session
from sqlalchemy import select
from uuid import UUID

from app.models.tenant import Tenant
from app.schemas.tenant import CreateTenant, TenantResponse

def create_tenant(db: Session, *, tenant_in: CreateTenant) -> TenantResponse:
    """
    Create a new tenant. This is a critical operation that should be restricted to platform administrators only.
    The tenant name must be unique to prevent conflicts.
    """
    try:
        tenant = Tenant(name=tenant_in.name, slug=tenant_in.slug)
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
        return TenantResponse.model_validate(tenant)
    except Exception as e:
        db.rollback()
        raise e
    
def get_tenant(db: Session, *, tenant_id: UUID) -> TenantResponse | None:
    """
    Get a tenant by its unique ID. This operation should be accessible to users who have permissions to view tenant information, such as platform administrators and tenant managers.
    """
    try:
        stmt = select(Tenant).where(Tenant.id == tenant_id)
        result = db.execute(stmt).scalar_one_or_none()
        if result is None:
            return None
        return TenantResponse.model_validate(result)
    except Exception as e:
        raise e
    
def list_tenants(db: Session) -> list[TenantResponse]:
    """
    List all tenants. Only platform administrators should have access to this operation, as it can expose sensitive information about the tenants in the system.
    """
    try:
        stmt = select(Tenant)
        results = db.execute(stmt).scalars().all()
        return [TenantResponse.model_validate(tenant) for tenant in results]
    except Exception as e:
        raise e
    
def get_tenant_by_slug(db: Session, *, slug: str) -> TenantResponse | None:
    """
    Get a tenant by its unique slug. This can be useful for operations that need to identify tenants by a human-readable identifier rather than a UUID.
    """
    try:
        stmt = select(Tenant).where(Tenant.slug == slug)
        result = db.execute(stmt).scalar_one_or_none()
        if result is None:
            return None
        return TenantResponse.model_validate(result)
    except Exception as e:
        raise e