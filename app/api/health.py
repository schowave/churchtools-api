from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health")
async def health() -> JSONResponse:
    # No version: it would tell anyone which known issues apply (the profile shows it to logged-in users)
    return JSONResponse({"status": "ok"})
