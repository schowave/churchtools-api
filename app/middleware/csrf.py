import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class CSRFMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, exempt_paths: list[str] | None = None):
        super().__init__(app)
        self.exempt_paths = set(exempt_paths or [])

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method in ("GET", "HEAD", "OPTIONS"):
            response = await call_next(request)
            token = secrets.token_urlsafe(32)
            response.set_cookie(
                "csrf_token",
                token,
                httponly=False,
                samesite="strict",
                secure=request.url.scheme == "https",
            )
            return response

        if request.url.path in self.exempt_paths:
            return await call_next(request)

        cookie_token = request.cookies.get("csrf_token")
        if not cookie_token:
            return JSONResponse({"error": "CSRF token missing"}, status_code=403)

        header_token = request.headers.get("X-CSRF-Token")
        if header_token and secrets.compare_digest(header_token, cookie_token):
            return await call_next(request)

        content_type = request.headers.get("content-type", "")
        if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
            form = await request.form()
            form_token = form.get("_csrf_token")
            if form_token and secrets.compare_digest(str(form_token), cookie_token):
                return await call_next(request)

        return JSONResponse({"error": "CSRF token mismatch"}, status_code=403)
