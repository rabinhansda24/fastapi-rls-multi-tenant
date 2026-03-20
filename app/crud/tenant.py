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
    stmt = select(Tenant).where(Tenant.id == tenant_id)
    result = db.execute(stmt).scalar_one_or_none()
    return TenantResponse.model_validate(result) if result else None

def list_tenants(db: Session) -> list[TenantResponse]:
    stmt = select(Tenant)
    return [TenantResponse.model_validate(t) for t in db.execute(stmt).scalars().all()]

def get_tenant_by_slug(db: Session, *, slug: str) -> TenantResponse | None:
    stmt = select(Tenant).where(Tenant.slug == slug)
    result = db.execute(stmt).scalar_one_or_none()
    return TenantResponse.model_validate(result) if result else None