import uvicorn
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=5005, reload=True)
