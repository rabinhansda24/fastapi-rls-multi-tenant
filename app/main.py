from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Logging must be initialised before any other app imports so that module-level
# loggers in routers/services are configured from the start.
from app.core.config import settings
from app.core.logging_config import get_logger, logging_manager

logging_manager.setup(level=settings.LOG_LEVEL, json_format=settings.LOG_JSON)
logger = get_logger(__name__)

# ---- Register third-party sinks here (after setup) ----
# Example:
#   from app.core.logging_config import LogSink
#   class SentrySink(LogSink):
#       def emit(self, record):
#           if record.levelno >= logging.ERROR:
#               sentry_sdk.capture_message(record.getMessage())
#   logging_manager.add_sink(SentrySink())

from app.api.health import router as health_router
from app.api.v1.ping import router as ping_router
from app.api.v1.user import router as user_router
from app.api.v1.auth import router as auth_router
from app.api.v1.tenant import router as tenant_router
from app.api.v1.cases import router as cases_router

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


@app.on_event("startup")
async def log_startup() -> None:
    logger.info(
        "Application started title=%s debug=%s log_level=%s log_json=%s",
        app.title,
        settings.DEBUG,
        settings.LOG_LEVEL,
        settings.LOG_JSON,
    )


@app.on_event("shutdown")
async def log_shutdown() -> None:
    logger.info("Application shutdown")
