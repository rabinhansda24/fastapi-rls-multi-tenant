from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.schemas.auth import LoginRequest, LoginResponse
from app.core.security import hash_password, verify_password, create_access_token
from app.crud.tenant import create_tenant
from app.crud.user import create_user, get_user_by_email
from app.domain.roles import UserRole
from app.schemas.auth import TenantRegistrationRequest, TenantRegistrationResponse, TokenClaims
from app.utils.slug import generate_unique_slug
from app.schemas.tenant import TenantResponse, CreateTenant
from app.schemas.user import CreateUser

logger = get_logger(__name__)

def register_tenant(request: TenantRegistrationRequest, db: Session) -> TenantRegistrationResponse:
    """
    Register a new tenant along with an admin user. Returns an access token for the admin user.
    - **name**: Name of the tenant
    - **admin_name**: Name of the admin user
    - **admin_email**: Email of the admin user
    - **admin_password**: Password for the admin user"""
    logger.info("Registering tenant name=%s admin_email=%s", request.name, request.admin_email)
    slug = generate_unique_slug(db, name=request.name)
    new_tenant: CreateTenant = CreateTenant(name=request.name, slug=slug)
    tenant = create_tenant(db, tenant_in=new_tenant)
    hashed_password = hash_password(request.admin_password)
    admin_user: CreateUser = CreateUser(
        name=request.admin_name,
        email=request.admin_email,
        password=request.admin_password,
        role=UserRole.ADMIN
    )
    user = create_user(db, user_in=admin_user, tenant_id=tenant.id, password_hash=hashed_password)
    token_claims: TokenClaims = TokenClaims(tenant_id=tenant.id, user_id=user.id)
    token = create_access_token(token_claims=token_claims)
    logger.info("Registered tenant tenant_id=%s admin_user_id=%s slug=%s", tenant.id, user.id, slug)
    return TenantRegistrationResponse(access_token=token.access_token, token_type=token.token_type, tenant_id=tenant.id)

def login_tenant(db: Session, trequest: LoginRequest, tenant: TenantResponse) -> LoginResponse:
    """
    Authenticate a user and obtain an access token for subsequent requests.
    - **email**: Email of the user
    - **password**: Password of the user
    """
    logger.info("Authenticating user tenant_id=%s email=%s", tenant.id, trequest.email)
    user = get_user_by_email(db, email=trequest.email, tenant_id=tenant.id)
    if not user:
        logger.warning("Login failed unknown email tenant_id=%s email=%s", tenant.id, trequest.email)
        raise ValueError("Invalid email or password")
    if not verify_password(trequest.password, user.password_hash):
        logger.warning("Login failed invalid password tenant_id=%s email=%s", tenant.id, trequest.email)
        raise ValueError("Invalid email or password")
    token_claims: TokenClaims = TokenClaims(tenant_id=tenant.id, user_id=user.id)
    token = create_access_token(token_claims=token_claims)
    logger.info("Login succeeded tenant_id=%s user_id=%s", tenant.id, user.id)
    return LoginResponse(access_token=token.access_token, token_type=token.token_type)
