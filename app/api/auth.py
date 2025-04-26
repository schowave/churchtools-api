from fastapi import APIRouter, Depends, HTTPException, status, Response, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import httpx
from app.config import Config
from typing import Optional

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "base_url": Config.CHURCHTOOLS_BASE, "version": Config.VERSION})

@router.post("/")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    data = {"password": password, "rememberMe": True, "username": username}
    
    async with httpx.AsyncClient() as client:
        response = await client.post(f'{Config.CHURCHTOOLS_BASE_URL}/api/login', json=data)
        
        if response.status_code == 200:
            person_id = response.json()['data']['personId']
            token_response = await client.get(
                f'{Config.CHURCHTOOLS_BASE_URL}/api/persons/{person_id}/logintoken',
                cookies=response.cookies
            )
            
            if token_response.status_code == 200:
                login_token = token_response.json()['data']
                redirect = RedirectResponse(url="/overview", status_code=status.HTTP_303_SEE_OTHER)
                redirect.set_cookie(key="login_token", value=login_token)
                return redirect
            else:
                return templates.TemplateResponse(
                    "login.html",
                    {"request": request, "base_url": Config.CHURCHTOOLS_BASE, "error": "Failed to retrieve login token.", "version": Config.VERSION}
                )
        else:
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "base_url": Config.CHURCHTOOLS_BASE, "error": "Invalid username or password.", "version": Config.VERSION}
            )

@router.post("/logout")
async def logout():
    response = RedirectResponse(url="/overview", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key="login_token")
    return response

@router.get("/overview")
async def overview(request: Request):
    login_token = request.cookies.get("login_token")
    if not login_token:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    
    return templates.TemplateResponse(
        "overview.html",
        {"request": request, "base_url": Config.CHURCHTOOLS_BASE, "version": Config.VERSION}
    )