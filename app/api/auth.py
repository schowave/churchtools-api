import httpx
from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse

from app.config import settings
from app.dependencies import get_http_client
from app.shared import templates

router = APIRouter()


@router.get("/")
async def login_page(request: Request):
    login_token = request.cookies.get(settings.cookie_login_token)
    if login_token:
        return RedirectResponse(url="/appointments", status_code=status.HTTP_303_SEE_OTHER)

    context = {"request": request, "base_url": settings.churchtools_base, "version": settings.version}
    return templates.TemplateResponse("login.html", context)


@router.post("/")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    client: httpx.AsyncClient = Depends(get_http_client),
):
    data = {"password": password, "rememberMe": True, "username": username}

    response = await client.post(f"{settings.churchtools_base_url}/api/login", json=data)

    if response.status_code == 200:
        person_id = response.json()["data"]["personId"]
        # Use session cookies from the login response to retrieve the long-lived login token.
        # The OpenAPI spec documents Authorization header auth for this endpoint,
        # but right after login we only have session cookies (no login token yet).
        token_response = await client.get(
            f"{settings.churchtools_base_url}/api/persons/{person_id}/logintoken", cookies=response.cookies
        )

        if token_response.status_code == 200:
            login_token = token_response.json()["data"]
            redirect = RedirectResponse(url="/appointments", status_code=status.HTTP_303_SEE_OTHER)
            is_https = request.url.scheme == "https"
            redirect.set_cookie(
                key=settings.cookie_login_token,
                value=login_token,
                httponly=True,
                secure=is_https,
                samesite="strict" if is_https else "lax",
            )
            return redirect
        else:
            return templates.TemplateResponse(
                "login.html",
                {
                    "request": request,
                    "base_url": settings.churchtools_base,
                    "error": "Login-Token konnte nicht abgerufen werden.",
                    "version": settings.version,
                },
            )
    else:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "base_url": settings.churchtools_base,
                "error": "Benutzername oder Passwort ungültig.",
                "version": settings.version,
            },
        )


@router.post("/logout")
async def logout(request: Request, client: httpx.AsyncClient = Depends(get_http_client)):
    login_token = request.cookies.get(settings.cookie_login_token)
    if login_token:
        try:
            await client.post(
                f"{settings.churchtools_base_url}/api/logout",
                headers={"Authorization": f"Login {login_token}"},
            )
        except Exception:
            pass  # Best-effort: still clear local cookie even if API call fails

    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key=settings.cookie_login_token)
    return response


@router.get("/overview")
async def overview(request: Request):
    login_token = request.cookies.get(settings.cookie_login_token)
    if not login_token:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        "overview.html", {"request": request, "base_url": settings.churchtools_base, "version": settings.version}
    )
