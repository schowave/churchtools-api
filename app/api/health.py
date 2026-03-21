from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import settings

router = APIRouter()


@router.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "version": settings.version})
