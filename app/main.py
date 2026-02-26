from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Load environment variables from .env file
load_dotenv()

from app.api import appointments, auth
from app.config import Config
from app.database import create_schema

Config.validate()

# Create FastAPI application
app = FastAPI(title="ChurchTools API")

# Include static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Make sure the directories for saved files and DB exist
Path(Config.FILE_DIRECTORY).mkdir(parents=True, exist_ok=True)
Path(Config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)

# Include routes
app.include_router(auth.router, tags=["auth"])
app.include_router(appointments.router, tags=["appointments"])


# Create database schema
create_schema()
