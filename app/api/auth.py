import httpx
from fastapi import APIRouter, Form, Request, status
from fastapi.responses import RedirectResponse

from app.config import Config
from app.shared import templates

router = APIRouter()


@router.get("/")
async def login_page(request: Request):
    login_token = request.cookies.get(Config.COOKIE_LOGIN_TOKEN)
    if login_token:
        return RedirectResponse(url="/appointments", status_code=status.HTTP_303_SEE_OTHER)

    context = {"request": request, "base_url": Config.CHURCHTOOLS_BASE, "version": Config.VERSION}
    return templates.TemplateResponse("login.html", context)


@router.post("/")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    data = {"password": password, "rememberMe": True, "username": username}

    async with httpx.AsyncClient() as client:
        response = await client.post(f"{Config.CHURCHTOOLS_BASE_URL}/api/login", json=data)

        if response.status_code == 200:
            person_id = response.json()["data"]["personId"]
            token_response = await client.get(
                f"{Config.CHURCHTOOLS_BASE_URL}/api/persons/{person_id}/logintoken", cookies=response.cookies
            )

            if token_response.status_code == 200:
                login_token = token_response.json()["data"]
                redirect = RedirectResponse(url="/appointments", status_code=status.HTTP_303_SEE_OTHER)
                redirect.set_cookie(
                    key=Config.COOKIE_LOGIN_TOKEN,
                    value=login_token,
                    httponly=True,
                    samesite="lax",
                )
                return redirect
            else:
                return templates.TemplateResponse(
                    "login.html",
                    {
                        "request": request,
                        "base_url": Config.CHURCHTOOLS_BASE,
                        "error": "Login-Token konnte nicht abgerufen werden.",
                        "version": Config.VERSION,
                    },
                )
        else:
            return templates.TemplateResponse(
                "login.html",
                {
                    "request": request,
                    "base_url": Config.CHURCHTOOLS_BASE,
                    "error": "Benutzername oder Passwort ungültig.",
                    "version": Config.VERSION,
                },
            )


@router.post("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key=Config.COOKIE_LOGIN_TOKEN)
    return response


@router.get("/overview")
async def overview(request: Request):
    login_token = request.cookies.get(Config.COOKIE_LOGIN_TOKEN)
    if not login_token:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        "overview.html", {"request": request, "base_url": Config.CHURCHTOOLS_BASE, "version": Config.VERSION}
    )
