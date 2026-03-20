from sqlalchemy.orm import Session
from sqlalchemy import select
from uuid import UUID

from app.core.logging_config import get_logger
from app.models.tenant import Tenant
from app.schemas.tenant import CreateTenant, TenantResponse

logger = get_logger(__name__)

def create_tenant(db: Session, *, tenant_in: CreateTenant) -> TenantResponse:
    """
    Create a new tenant. This is a critical operation that should be restricted to platform administrators only.
    """
    tenant = Tenant(name=tenant_in.name, slug=tenant_in.slug)
    db.add(tenant)
    db.flush()  # populate id via RETURNING; dependency commits the transaction
    logger.info("Created tenant tenant_id=%s slug=%s", tenant.id, tenant.slug)
    return TenantResponse.model_validate(tenant)
    
def get_tenant(db: Session, *, tenant_id: UUID) -> TenantResponse | None:
    logger.debug("Fetching tenant tenant_id=%s", tenant_id)
    stmt = select(Tenant).where(Tenant.id == tenant_id)
    result = db.execute(stmt).scalar_one_or_none()
    return TenantResponse.model_validate(result) if result else None

def list_tenants(db: Session) -> list[TenantResponse]:
    logger.debug("Listing tenants")
    stmt = select(Tenant)
    return [TenantResponse.model_validate(t) for t in db.execute(stmt).scalars().all()]

def get_tenant_by_slug(db: Session, *, slug: str) -> TenantResponse | None:
    logger.debug("Fetching tenant by slug slug=%s", slug)
    stmt = select(Tenant).where(Tenant.slug == slug)
    result = db.execute(stmt).scalar_one_or_none()
    return TenantResponse.model_validate(result) if result else None
