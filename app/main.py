from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request, status
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

# Load environment variables from .env file
load_dotenv()

from app.api import appointments, auth
from app.config import Config
from app.database import create_schema
from app.shared import templates

# Create FastAPI application
app = FastAPI(title="ChurchTools API")

# Include static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Make sure the directory for saved files exists
Path(Config.FILE_DIRECTORY).mkdir(parents=True, exist_ok=True)

# Include routes
app.include_router(auth.router, tags=["auth"])
app.include_router(appointments.router, tags=["appointments"])


# Main route
@app.get("/")
async def root(request: Request):
    login_token = request.cookies.get(Config.COOKIE_LOGIN_TOKEN)
    if login_token:
        return RedirectResponse(url="/overview", status_code=status.HTTP_303_SEE_OTHER)
    context = {"request": request, "base_url": Config.CHURCHTOOLS_BASE, "version": Config.VERSION}
    return templates.TemplateResponse("login.html", context)


# Create database schema
create_schema()
