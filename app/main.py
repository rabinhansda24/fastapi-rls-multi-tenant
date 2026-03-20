from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.v1.ping import router as ping_router
from app.api.v1.user import router as user_router
from app.api.v1.auth import router as auth_router
from app.api.v1.tenant import router as tenant_router
from app.api.v1.cases import router as cases_router
from app.core.config import settings

app = FastAPI(
    title="FastAPI Multi-Tenant RLS API",
    description="Multi-tenant REST API with PostgreSQL Row-Level Security isolation.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(ping_router)
app.include_router(auth_router, prefix="/v1")
app.include_router(user_router, prefix="/v1")
app.include_router(tenant_router, prefix="/v1")
app.include_router(cases_router, prefix="/v1")