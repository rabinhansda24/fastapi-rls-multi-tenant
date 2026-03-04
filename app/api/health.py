from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("/", summary="Health Check", description="Check the health of the application.")
async def health_check():
    return {"status": "healthy"}