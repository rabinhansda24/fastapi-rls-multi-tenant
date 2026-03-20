from fastapi import APIRouter

from app.core.logging_config import get_logger

router = APIRouter(prefix="/health", tags=["Health"])
logger = get_logger(__name__)

@router.get("/", summary="Health Check", description="Check the health of the application.")
async def health_check():
    logger.debug("Health check requested")
    return {"status": "healthy"}
