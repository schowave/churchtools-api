from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import appointments, auth, health
from app.config import settings
from app.logging_config import configure_logging

configure_logging(settings.log_format)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient(timeout=30.0)
    yield
    await app.state.http_client.aclose()


# Create FastAPI application
app = FastAPI(title="ChurchTools API", lifespan=lifespan)
app.add_middleware(SecurityHeadersMiddleware)

# Include static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Make sure the directory for DB exists
Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)

# Include routes
app.include_router(health.router, tags=["health"])
app.include_router(auth.router, tags=["auth"])
app.include_router(appointments.router, tags=["appointments"])
