from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
from pathlib import Path
from dotenv import load_dotenv

# Lade Umgebungsvariablen aus .env-Datei
load_dotenv()

from app.database import create_schema
from app.config import Config
from app.api import auth, appointments

# FastAPI-Anwendung erstellen
app = FastAPI(title="ChurchTools API")

# Statische Dateien einbinden
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates einrichten
templates = Jinja2Templates(directory="app/templates")

# Make sure the directory for saved files exists
Path(Config.FILE_DIRECTORY).mkdir(parents=True, exist_ok=True)

# Routen einbinden
app.include_router(auth.router, tags=["auth"])
app.include_router(appointments.router, tags=["appointments"])

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