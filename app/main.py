from contextlib import asynccontextmanager
from pathlib import Path

import httpx2
import structlog
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import appointments, auth, events, health, images
from app.config import APP_DIR, settings
from app.logging_config import configure_logging
from app.middleware.csrf import CSRFMiddleware

configure_logging(settings.log_format)
logger = structlog.get_logger()


# No inline scripts or eval; styles allow inline style attributes and Google Fonts.
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "font-src 'self' https://fonts.gstatic.com",
        "img-src 'self' data: blob:",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        # Routes may set a stricter policy (e.g. served images)
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.crud import cleanup_orphaned_settings
    from app.database import SessionLocal
    from app.services.sessions import purge_expired_sessions

    db = SessionLocal()
    try:
        cleanup_orphaned_settings(db)
    finally:
        db.close()
    purge_expired_sessions()

    app.state.http_client = httpx2.AsyncClient(timeout=30.0)
    yield
    await app.state.http_client.aclose()


# Create FastAPI application
app = FastAPI(title="ChurchTools API", lifespan=lifespan)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSRFMiddleware, exempt_paths=["/health"])

# Include static files
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")

# Make sure the directory for DB exists
Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)


@app.exception_handler(401)
async def unauthorized_handler(request: Request, exc):
    return JSONResponse({"error": "unauthorized", "detail": str(exc.detail)}, status_code=401)


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse({"error": "not_found", "detail": str(exc.detail)}, status_code=404)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    # Only field location and message: str(exc) echoes the request input and server file paths.
    detail = [{"loc": list(err.get("loc", ())), "msg": err.get("msg", "")} for err in exc.errors()]
    logger.info("request_validation_failed", path=request.url.path, errors=detail)
    return JSONResponse({"error": "validation_error", "detail": detail}, status_code=422)


# Include routes
app.include_router(health.router, tags=["health"])
app.include_router(auth.router, tags=["auth"])
app.include_router(appointments.router, tags=["appointments"])
app.include_router(images.router, tags=["images"])
app.include_router(events.router, tags=["events"])
