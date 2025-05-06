from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from app.database import create_schema
from app.config import Config
from app.api import auth, appointments

# Create FastAPI application
app = FastAPI(title="ChurchTools API")

# Include static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Set up templates
templates = Jinja2Templates(directory="app/templates")

# Make sure the directory for saved files exists
Path(Config.FILE_DIRECTORY).mkdir(parents=True, exist_ok=True)

# Include routes
app.include_router(auth.router, tags=["auth"])
app.include_router(appointments.router, tags=["appointments"])

# Main route
@app.get("/")
async def root(request: Request):
    login_token = request.cookies.get("login_token")
    if login_token:
        return RedirectResponse(url="/overview", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("login.html", {"request": request, "base_url": Config.CHURCHTOOLS_BASE, "version": Config.VERSION})

# Create database schema
create_schema()

# Start server with uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=5005, reload=True)