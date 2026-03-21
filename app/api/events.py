from typing import List, Optional

import httpx
import structlog
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from starlette import status

from app.config import settings
from app.dependencies import get_http_client
from app.services.churchtools_client import (
    AuthenticationError,
    fetch_agenda,
    fetch_calendars,
    fetch_events,
)
from app.shared import templates
from app.utils import get_date_range_from_form

logger = structlog.get_logger()
router = APIRouter()


@router.get("/api/events")
async def api_events(
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
    start_date: str = Query(...),
    end_date: str = Query(...),
    calendar_ids: List[str] = Query(...),
) -> JSONResponse:
    """JSON endpoint returning events with their service assignments."""
    login_token = request.cookies.get(settings.cookie_login_token)
    if not login_token:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)

    try:
        events = await fetch_events(login_token, start_date, end_date, calendar_ids, client)
    except AuthenticationError:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)

    return JSONResponse({"events": [ev.model_dump() for ev in events]})


@router.get("/api/events/{event_id}/agenda")
async def api_event_agenda(
    request: Request,
    event_id: int,
    client: httpx.AsyncClient = Depends(get_http_client),
) -> JSONResponse:
    """JSON endpoint returning the agenda for a single event."""
    login_token = request.cookies.get(settings.cookie_login_token)
    if not login_token:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)

    try:
        items = await fetch_agenda(login_token, event_id, client)
    except AuthenticationError:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)

    return JSONResponse({"items": [item.model_dump() for item in items]})
