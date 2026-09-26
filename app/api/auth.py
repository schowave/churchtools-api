from datetime import UTC

import httpx2
import structlog
from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse, Response

from app.config import settings
from app.services import sessions
from app.services.auth import (
    clear_session_cookies,
    forget_login_token,
    get_valid_login_token,
    redirect_to_login,
    set_session_cookie,
)
from app.services.churchtools_client import AuthenticationError, fetch_current_user
from app.services.rate_limit import LoginRateLimiter
from app.web import get_http_client, templates

logger = structlog.get_logger()
router = APIRouter()

# Failed logins are counted per username and per client IP. A success only clears the username's
# count: clearing the IP too would let anyone with an account reset the limit between guesses.
login_rate_limiter = LoginRateLimiter()
# Looser, since a whole congregation may share one IP (church WiFi, proxy without forwarded headers)
ip_rate_limiter = LoginRateLimiter(max_failures=20)

# Where users land after login; most sessions start with the slides
START_PAGE = "/appointments"


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _username_key(username: str) -> str:
    return username.strip().casefold()


def _login_error(request: Request, message: str, status_code: int = 200) -> Response:
    context = {"base_url": settings.churchtools_base, "error": message, "version": settings.version}
    return templates.TemplateResponse(request, "login.html", context, status_code=status_code)


@router.get("/")
async def login_page(request: Request) -> Response:
    if request.cookies.get(settings.cookie_session):
        return RedirectResponse(url=START_PAGE, status_code=status.HTTP_303_SEE_OTHER)

    context = {"base_url": settings.churchtools_base, "version": settings.version}
    if request.query_params.get("hinweis") == "abgelaufen":
        # Set by the CSRF middleware when a form was submitted from a page that had been open too long
        context["error"] = "Die Seite war zu lange geöffnet. Bitte erneut anmelden."
    return templates.TemplateResponse(request, "login.html", context)


@router.post("/")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    client: httpx2.AsyncClient = Depends(get_http_client),
) -> Response:
    client_key = _client_key(request)
    username_key = _username_key(username)
    retry_after = max(login_rate_limiter.retry_after(username_key), ip_rate_limiter.retry_after(client_key))
    if retry_after:
        minutes = max(1, round(retry_after / 60))
        response = _login_error(
            request,
            f"Zu viele Fehlversuche. Bitte in {minutes} Minute{'n' if minutes != 1 else ''} erneut versuchen.",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )
        response.headers["Retry-After"] = str(retry_after)
        return response

    data = {"password": password, "rememberMe": True, "username": username}

    try:
        response = await client.post(f"{settings.churchtools_base_url}/api/login", json=data)
        if response.status_code != 200:
            login_rate_limiter.record_failure(username_key)
            ip_rate_limiter.record_failure(client_key)
            return _login_error(request, "Benutzername oder Passwort ungültig.")

        login_rate_limiter.record_success(username_key)
        person_id = response.json()["data"]["personId"]
        # Use session cookies from the login response to retrieve the long-lived login token.
        # The OpenAPI spec documents Authorization header auth for this endpoint,
        # but right after login we only have session cookies (no login token yet).
        token_response = await client.get(
            f"{settings.churchtools_base_url}/api/persons/{person_id}/logintoken", cookies=response.cookies
        )
        if token_response.status_code != 200:
            return _login_error(request, "Login-Token konnte nicht abgerufen werden.")
        login_token = token_response.json()["data"]
    except httpx2.HTTPError as exc:
        logger.warning("login_churchtools_unreachable", error=type(exc).__name__)
        return _login_error(
            request, "ChurchTools ist gerade nicht erreichbar. Bitte später erneut versuchen.", status_code=502
        )
    except (ValueError, KeyError, TypeError) as exc:
        # Not JSON or not the expected shape (e.g. an HTML error page, or a login step we do not support)
        logger.warning("login_unexpected_response", error=type(exc).__name__)
        return _login_error(request, "Unerwartete Antwort von ChurchTools. Anmeldung nicht möglich.", status_code=502)

    redirect = RedirectResponse(url=START_PAGE, status_code=status.HTTP_303_SEE_OTHER)
    # The browser only gets a random session id; the token stays on the server
    set_session_cookie(redirect, request, await run_in_threadpool(sessions.create_session, login_token))
    return redirect


@router.post("/logout")
async def logout(request: Request, client: httpx2.AsyncClient = Depends(get_http_client)) -> RedirectResponse:
    session_id = request.cookies.get(settings.cookie_session)
    login_token = await run_in_threadpool(sessions.get_session_token, session_id) if session_id else None
    if session_id:
        await run_in_threadpool(sessions.delete_session, session_id)
    if login_token:
        forget_login_token(login_token)
        try:
            await client.post(
                f"{settings.churchtools_base_url}/api/logout",
                headers={"Authorization": f"Login {login_token}"},
            )
        except Exception:
            pass  # Best-effort: the local session is gone either way

    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    clear_session_cookies(response, request)
    return response


@router.get("/overview")
async def overview() -> RedirectResponse:
    """The former start page; kept as a redirect for bookmarks."""
    return RedirectResponse(url=START_PAGE, status_code=status.HTTP_301_MOVED_PERMANENTLY)


@router.get("/profile")
async def profile(request: Request, client: httpx2.AsyncClient = Depends(get_http_client)) -> Response:
    login_token = await get_valid_login_token(request, client)
    if not login_token:
        return redirect_to_login(request)

    try:
        user = await fetch_current_user(login_token, client)
    except AuthenticationError:
        return redirect_to_login(request)
    except (httpx2.HTTPError, ValueError, KeyError, TypeError) as exc:
        # The page still has to offer logout when ChurchTools is down
        logger.warning("profile_user_fetch_failed", error=type(exc).__name__)
        user = None

    session_id = request.cookies.get(settings.cookie_session)
    expires_at = await run_in_threadpool(sessions.get_session_expiry, session_id)
    expires_local = expires_at.replace(tzinfo=UTC).astimezone(settings.timezone) if expires_at else None

    context = {
        "base_url": settings.churchtools_base,
        "churchtools_url": settings.churchtools_base_url,
        "version": settings.version,
        "user": user,
        "session_expires": expires_local.strftime("%d.%m.%Y, %H:%M Uhr") if expires_local else None,
    }
    return templates.TemplateResponse(request, "profile.html", context)
