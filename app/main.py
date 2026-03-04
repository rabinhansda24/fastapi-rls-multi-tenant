from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.v1.ping import router as ping_router

app = FastAPI(
    title="FastAPI Template",
    description="A template for building FastAPI applications.",
    version="1.0.0",
)

app.include_router(health_router)
app.include_router(ping_router)