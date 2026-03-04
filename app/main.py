from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.v1.ping import router as ping_router
from app.api.v1.user import router as user_router
from app.api.v1.auth import router as auth_router
from app.api.v1.tenant import router as tenant_router

app = FastAPI(
    title="FastAPI Template",
    description="A template for building FastAPI applications.",
    version="1.0.0",
)

app.include_router(health_router)
app.include_router(ping_router)
app.include_router(auth_router, prefix="/v1", tags=["Authentication"])
app.include_router(user_router, prefix="/v1", tags=["Users"])
app.include_router(tenant_router, prefix="/v1", tags=["Tenants"])