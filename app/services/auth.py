import hashlib
import time

import httpx2
from fastapi import Request, status
from fastapi.responses import RedirectResponse, Response

from app.config import settings
from app.services import sessions

# Cookie name used before server-side sessions; it held the raw ChurchTools token.
LEGACY_TOKEN_COOKIE = "login_token"

TOKEN_CACHE_TTL_SECONDS = 300

# sha256(token) -> expiry timestamp. Only successful validations are cached.
_valid_token_cache: dict[str, float] = {}


def _cache_key(login_token: str) -> str:
    return hashlib.sha256(login_token.encode()).hexdigest()


async def validate_login_token(login_token: str, client: httpx2.AsyncClient) -> bool:
    """Check the token against ChurchTools.

    ChurchTools answers /api/whoami with HTTP 200 and the anonymous user (id -1)
    for invalid tokens, so the person id must be checked, not only the status.
    """
    key = _cache_key(login_token)
    now = time.monotonic()
    expiry = _valid_token_cache.get(key)
    if expiry is not None and expiry > now:
        return True

    response = await client.get(
        f"{settings.churchtools_base_url}/api/whoami",
        headers={"Authorization": f"Login {login_token}"},
    )
    if response.status_code in (401, 403):
        return False
    response.raise_for_status()

    person_id = response.json().get("data", {}).get("id", -1)
    if not isinstance(person_id, int) or person_id <= 0:
        return False

    for cached_key, cached_expiry in list(_valid_token_cache.items()):
        if cached_expiry <= now:
            del _valid_token_cache[cached_key]
    _valid_token_cache[key] = now + TOKEN_CACHE_TTL_SECONDS
    return True


def forget_login_token(login_token: str) -> None:
    """Drop a token from the validation cache (e.g. on logout)."""
    _valid_token_cache.pop(_cache_key(login_token), None)


async def get_valid_login_token(request: Request, client: httpx2.AsyncClient) -> str | None:
    """Return the ChurchTools token of the request's session if ChurchTools still accepts it, else None."""
    session_id = request.cookies.get(settings.cookie_session)
    if not session_id:
        return None
    login_token = sessions.get_session_token(session_id)
    if not login_token:
        return None
    if not await validate_login_token(login_token, client):
        # Token was revoked in ChurchTools: the session is useless
        sessions.delete_session(session_id)
        return None
    return login_token


def _cookie_options(request: Request) -> dict:
    is_https = request.url.scheme == "https"
    return {"httponly": True, "secure": is_https, "samesite": "strict" if is_https else "lax"}


def set_session_cookie(response: Response, request: Request, session_id: str) -> None:
    max_age = int(sessions.SESSION_LIFETIME.total_seconds())
    response.set_cookie(settings.cookie_session, session_id, max_age=max_age, **_cookie_options(request))


def clear_session_cookies(response: Response, request: Request) -> None:
    """Delete the session cookie with the attributes it was set with (browsers may ignore it otherwise)."""
    response.delete_cookie(settings.cookie_session, **_cookie_options(request))
    response.delete_cookie(LEGACY_TOKEN_COOKIE, **_cookie_options(request))


def redirect_to_login(request: Request) -> RedirectResponse:
    """Redirect to the login page and drop the (missing or rejected) session cookie."""
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    clear_session_cookies(response, request)
    return response
