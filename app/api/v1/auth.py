from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.auth import LoginRequest, LoginResponse
from app.service.auth import register_tenant, login_tenant
from app.schemas.auth import TenantRegistrationRequest, TenantRegistrationResponse
from app.db.public import get_db
from app.crud.tenant import get_tenant_by_slug

router = APIRouter(prefix="/auth", tags=["Authentication"])
@router.post("/register", response_model=TenantRegistrationResponse, summary="Register a new tenant", description="Register a new tenant along with an admin user. Returns an access token for the admin user.")
async def register_new_tenant(request: TenantRegistrationRequest, db=Depends(get_db)):
    """
    Register a new tenant along with an admin user. Returns an access token for the admin user.
    - **name**: Name of the tenant
    - **admin_name**: Name of the admin user
    - **admin_email**: Email of the admin user
    - **admin_password**: Password for the admin user"""
    try:
        return register_tenant(request, db=db)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    

@router.post("/{tenant_slug}/login", response_model=LoginResponse, summary="Login and obtain an access token", description="Authenticate a user and obtain an access token for subsequent requests.")
async def login(tenant_slug: str, trequest: LoginRequest, db=Depends(get_db)):
    """
    Authenticate a user and obtain an access token for subsequent requests.
    - **email**: Email of the user
    - **password**: Password of the user
    """
    try:
        tenant = get_tenant_by_slug(db, slug=tenant_slug)
        if not tenant:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requeste Forbidden")
        return login_tenant(db, trequest=trequest, tenant=tenant)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    

