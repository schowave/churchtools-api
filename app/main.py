from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Lade Umgebungsvariablen aus .env-Datei
load_dotenv()

from app.database import create_schema
from app.config import Config
from app.api import auth, appointments, api_endpoints
from app.utils.logging_config import setup_logging, APIError, log_exception

# Logging einrichten
loggers = setup_logging()
logger = logging.getLogger("app.main")

# FastAPI-Anwendung erstellen
app = FastAPI(
    title="ChurchTools API",
    description="API für die Integration mit ChurchTools",
    version=Config.VERSION
)

# CORS-Middleware hinzufügen
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In Produktion einschränken
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Statische Dateien einbinden
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates einrichten
templates = Jinja2Templates(directory="app/templates")

# Stellen Sie sicher, dass das Verzeichnis für gespeicherte Dateien existiert
Path(Config.FILE_DIRECTORY).mkdir(parents=True, exist_ok=True)

# Globale Fehlerbehandlung
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    logger.error(f"HTTP-Fehler: {exc.status_code} - {exc.detail}")
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "status_code": exc.status_code,
            "detail": exc.detail,
            "base_url": Config.CHURCHTOOLS_BASE,
            "version": Config.VERSION
        },
        status_code=exc.status_code
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    logger.error(f"Validierungsfehler: {str(exc)}")
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "status_code": 422,
            "detail": "Validierungsfehler in den Eingabedaten",
            "base_url": Config.CHURCHTOOLS_BASE,
            "version": Config.VERSION
        },
        status_code=422
    )

@app.exception_handler(APIError)
async def api_error_handler(request, exc):
    log_exception(logger, exc)
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "status_code": exc.status_code,
            "detail": exc.message,
            "base_url": Config.CHURCHTOOLS_BASE,
            "version": Config.VERSION
        },
        status_code=exc.status_code
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    log_exception(logger, exc, {"path": request.url.path})
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "status_code": 500,
            "detail": "Ein interner Serverfehler ist aufgetreten",
            "base_url": Config.CHURCHTOOLS_BASE,
            "version": Config.VERSION
        },
        status_code=500
    )

# Routen einbinden
app.include_router(auth.router, tags=["auth"])
app.include_router(appointments.router, tags=["appointments"])
app.include_router(api_endpoints.router)

# API-spezifische Fehlerbehandlung für JSON-Antworten
@app.exception_handler(APIError)
async def api_json_error_handler(request, exc):
    if request.url.path.startswith("/api/"):
        log_exception(logger, exc, {"path": request.url.path})
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.message,
                "details": exc.details
            }
        )
    # Für nicht-API-Routen wird der bestehende HTML-Fehlerhandler verwendet
    return await api_error_handler(request, exc)

# Startup-Event
@app.on_event("startup")
async def startup_event():
    logger.info(f"ChurchTools API v{Config.VERSION} gestartet")

# Hauptroute
@app.get("/")
async def root(request: Request):
    login_token = request.cookies.get("login_token")
    if login_token:
        return RedirectResponse(url="/overview", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("login.html", {"request": request, "base_url": Config.CHURCHTOOLS_BASE, "version": Config.VERSION})

# Datenbank-Schema erstellen
create_schema()

# Server starten mit uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=5005, reload=True)