import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response

COOKIE_NAME = "csrf_token"
# Without max_age the cookie dies with the browser session; mobile browsers drop those while a tab stays open.
COOKIE_MAX_AGE = 30 * 24 * 3600
# Login page shows a hint for this query value (see app/api/auth.py)
EXPIRED_FORM_REDIRECT = "/?hinweis=abgelaufen"


def _reject(request: Request) -> Response:
    """Plain HTML forms get sent back to the login page with a hint; JS callers get a code they can retry on."""
    content_type = request.headers.get("content-type", "")
    if "X-CSRF-Token" not in request.headers and "application/x-www-form-urlencoded" in content_type:
        return RedirectResponse(EXPIRED_FORM_REDIRECT, status_code=303)
    return JSONResponse(
        {"error": "csrf_failed", "detail": "Die Seite war zu lange geöffnet. Bitte neu laden und erneut versuchen."},
        status_code=403,
    )


class CSRFMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, exempt_paths: list[str] | None = None):
        super().__init__(app)
        self.exempt_paths = set(exempt_paths or [])

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method in ("GET", "HEAD", "OPTIONS"):
            # Reuse existing token so templates can read it from the incoming cookie.
            # Only generate a new one if no cookie exists yet.
            token = request.cookies.get(COOKIE_NAME) or secrets.token_urlsafe(32)
            # Expose the token to templates as request.state.csrf_token. request.state lives in the
            # ASGI scope and is shared with the endpoint's Request object; mutating request.cookies
            # here would not be, so a first visit would render an empty token.
            request.state.csrf_token = token

            response = await call_next(request)
            response.set_cookie(
                COOKIE_NAME,
                token,
                max_age=COOKIE_MAX_AGE,
                httponly=False,
                samesite="lax",
                secure=request.url.scheme == "https",
            )
            return response

        if request.url.path in self.exempt_paths:
            return await call_next(request)

        cookie_token = request.cookies.get(COOKIE_NAME)
        if not cookie_token:
            return _reject(request)
        # Templates rendered in response to a POST (e.g. failed login) need the token too.
        request.state.csrf_token = cookie_token

        header_token = request.headers.get("X-CSRF-Token")
        if header_token and secrets.compare_digest(header_token, cookie_token):
            return await call_next(request)

        content_type = request.headers.get("content-type", "")
        if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
            # Cache the body so downstream handlers (FastAPI Form()) can read it again
            body = await request.body()
            form = await request.form()
            form_token = form.get("_csrf_token")
            await form.close()
            # Re-inject cached body so FastAPI can parse it again
            request._body = body
            if form_token and secrets.compare_digest(str(form_token), cookie_token):
                return await call_next(request)

        return _reject(request)
