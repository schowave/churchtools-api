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


# No inline scripts or eval; styles allow inline style attributes. Fonts are self-hosted.
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "font-src 'self'",
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
        # The app needs none of these browser features
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        # Browsers ignore HSTS over plain HTTP; the scheme is https behind a trusted proxy (FORWARDED_ALLOW_IPS)
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        # Routes may set a stricter policy (e.g. served images)
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.sessions import purge_expired_sessions

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


@app.exception_handler(httpx2.HTTPError)
async def churchtools_error_handler(request: Request, exc: httpx2.HTTPError):
    # ChurchTools unreachable or answering with an error status (raise_for_status)
    logger.warning("churchtools_request_failed", path=request.url.path, error=type(exc).__name__, message=str(exc))
    detail = "ChurchTools ist gerade nicht erreichbar. Bitte später erneut versuchen."
    return JSONResponse({"error": "upstream_error", "detail": detail}, status_code=502)


@app.exception_handler(Exception)
async def internal_error_handler(request: Request, exc: Exception):
    # Starlette re-raises the exception after this handler, so the traceback is still logged by uvicorn
    logger.error("unhandled_exception", path=request.url.path, error=type(exc).__name__)
    detail = "Interner Fehler. Bitte erneut versuchen."
    return JSONResponse({"error": "internal_error", "detail": detail}, status_code=500)


# Include routes
app.include_router(health.router, tags=["health"])
app.include_router(auth.router, tags=["auth"])
app.include_router(appointments.router, tags=["appointments"])
app.include_router(images.router, tags=["images"])
app.include_router(events.router, tags=["events"])
