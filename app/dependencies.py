import httpx2
from fastapi import Request


def get_http_client(request: Request) -> httpx2.AsyncClient:
    return request.app.state.http_client
