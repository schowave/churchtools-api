import uvicorn
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from app.main import app

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=5005, reload=True)