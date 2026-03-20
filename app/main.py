from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import appointments, auth
from app.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


# Create FastAPI application
app = FastAPI(title="ChurchTools API")
app.add_middleware(SecurityHeadersMiddleware)

# Include static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Make sure the directories for saved files and DB exist
Path(settings.file_directory).mkdir(parents=True, exist_ok=True)
Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)

# Include routes
app.include_router(auth.router, tags=["auth"])
app.include_router(appointments.router, tags=["appointments"])
