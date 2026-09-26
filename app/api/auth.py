import httpx2
from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse, Response

from app.config import settings
from app.dependencies import get_http_client
from app.services import sessions
from app.services.auth import (
    clear_session_cookies,
    forget_login_token,
    get_valid_login_token,
    redirect_to_login,
    set_session_cookie,
)
from app.services.rate_limit import LoginRateLimiter
from app.shared import templates

router = APIRouter()

login_rate_limiter = LoginRateLimiter()


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _login_error(request: Request, message: str, status_code: int = 200) -> Response:
    context = {"base_url": settings.churchtools_base, "error": message, "version": settings.version}
    return templates.TemplateResponse(request, "login.html", context, status_code=status_code)


@router.get("/")
async def login_page(request: Request) -> Response:
    if request.cookies.get(settings.cookie_session):
        return RedirectResponse(url="/overview", status_code=status.HTTP_303_SEE_OTHER)

    context = {"base_url": settings.churchtools_base, "version": settings.version}
    return templates.TemplateResponse(request, "login.html", context)


@router.post("/")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    client: httpx2.AsyncClient = Depends(get_http_client),
) -> Response:
    client_key = _client_key(request)
    retry_after = login_rate_limiter.retry_after(client_key)
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

    response = await client.post(f"{settings.churchtools_base_url}/api/login", json=data)

    if response.status_code == 200:
        login_rate_limiter.record_success(client_key)
        person_id = response.json()["data"]["personId"]
        # Use session cookies from the login response to retrieve the long-lived login token.
        # The OpenAPI spec documents Authorization header auth for this endpoint,
        # but right after login we only have session cookies (no login token yet).
        token_response = await client.get(
            f"{settings.churchtools_base_url}/api/persons/{person_id}/logintoken", cookies=response.cookies
        )

        if token_response.status_code == 200:
            login_token = token_response.json()["data"]
            redirect = RedirectResponse(url="/overview", status_code=status.HTTP_303_SEE_OTHER)
            # The browser only gets a random session id; the token stays on the server
            set_session_cookie(redirect, request, sessions.create_session(login_token))
            return redirect
        else:
            return _login_error(request, "Login-Token konnte nicht abgerufen werden.")
    else:
        login_rate_limiter.record_failure(client_key)
        return _login_error(request, "Benutzername oder Passwort ungültig.")


@router.post("/logout")
async def logout(request: Request, client: httpx2.AsyncClient = Depends(get_http_client)) -> RedirectResponse:
    session_id = request.cookies.get(settings.cookie_session)
    login_token = sessions.get_session_token(session_id) if session_id else None
    if session_id:
        sessions.delete_session(session_id)
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
async def overview(request: Request, client: httpx2.AsyncClient = Depends(get_http_client)) -> Response:
    if not await get_valid_login_token(request, client):
        return redirect_to_login(request)

    return templates.TemplateResponse(
        request, "overview.html", {"base_url": settings.churchtools_base, "version": settings.version}
    )
