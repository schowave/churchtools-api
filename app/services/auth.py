import hashlib
import time

import httpx
from fastapi import Request, status
from fastapi.responses import RedirectResponse

from app.config import settings

TOKEN_CACHE_TTL_SECONDS = 300

# sha256(token) -> expiry timestamp. Only successful validations are cached.
_valid_token_cache: dict[str, float] = {}


def _cache_key(login_token: str) -> str:
    return hashlib.sha256(login_token.encode()).hexdigest()


async def validate_login_token(login_token: str, client: httpx.AsyncClient) -> bool:
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


async def get_valid_login_token(request: Request, client: httpx.AsyncClient) -> str | None:
    """Return the login token from the cookie if ChurchTools accepts it, else None."""
    login_token = request.cookies.get(settings.cookie_login_token)
    if not login_token:
        return None
    if not await validate_login_token(login_token, client):
        return None
    return login_token


def redirect_to_login() -> RedirectResponse:
    """Redirect to the login page and drop the (missing or rejected) login cookie."""
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key=settings.cookie_login_token)
    return response
