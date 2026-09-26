import httpx2
from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.config import APP_DIR

templates = Jinja2Templates(directory=APP_DIR / "templates")


def get_http_client(request: Request) -> httpx2.AsyncClient:
    return request.app.state.http_client
