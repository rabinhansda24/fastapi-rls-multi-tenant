from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID

from app.schemas.ping import CreatePing, PingResponse
from app.core.logging_config import get_logger
from app.crud.ping import create_ping, get_ping, list_pings

from app.db.public import get_db

router = APIRouter(prefix="/ping", tags=["Ping"])
logger = get_logger(__name__)

@router.post("/", response_model=PingResponse, summary="Create a new ping", description="Create a new ping with the provided name and age.")
async def create_new_ping(ping_in: CreatePing, db=Depends(get_db)):
    try:
        logger.info("Creating ping name=%s age=%s", ping_in.name, ping_in.age)
        return create_ping(db, ping_in=ping_in)
    except Exception as e:
        logger.exception("Failed to create ping name=%s", ping_in.name)
        raise HTTPException(status_code=400, detail=str(e))
    

@router.get("/{ping_id}", response_model=PingResponse, summary="Get a ping by ID", description="Retrieve a ping by its unique ID.")
async def get_ping_by_id(ping_id: UUID, db=Depends(get_db)):
    try:
        logger.debug("Fetching ping ping_id=%s", ping_id)
        ping = get_ping(db, ping_id=ping_id)
        if ping is None:
            logger.warning("Ping not found ping_id=%s", ping_id)
            raise HTTPException(status_code=404, detail="Ping not found")
        return ping
    except Exception as e:
        logger.exception("Failed to fetch ping ping_id=%s", ping_id)
        raise HTTPException(status_code=400, detail=str(e))
    

@router.get("/", response_model=list[PingResponse], summary="List all pings", description="Retrieve a list of all pings.")
async def list_all_pings(db=Depends(get_db)):
    try:
        logger.debug("Listing pings")
        return list_pings(db)
    except Exception as e:
        logger.exception("Failed to list pings")
        raise HTTPException(status_code=400, detail=str(e))
