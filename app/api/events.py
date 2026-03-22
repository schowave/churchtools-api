from datetime import datetime
from io import BytesIO
from typing import List, Optional

import httpx
import structlog
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response, StreamingResponse
from starlette import status

from app.config import settings
from app.dependencies import get_http_client
from app.services.churchtools_client import (
    AuthenticationError,
    fetch_agenda,
    fetch_calendars,
    fetch_events,
)
from app.services.pdf_generator import create_agenda_pdf, create_services_pdf
from app.shared import templates
from app.utils import get_date_range_from_form

logger = structlog.get_logger()
router = APIRouter()


@router.get("/agenda")
async def agenda_page(
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    calendar_ids: Optional[List[str]] = Query(None),
) -> Response:
    """Agenda page — shows worship service rundowns."""
    login_token = request.cookies.get(settings.cookie_login_token)
    if not login_token:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    if not start_date or not end_date:
        start_date_default, end_date_default = get_date_range_from_form()
        start_date = start_date or start_date_default
        end_date = end_date or end_date_default

    try:
        calendars = await fetch_calendars(login_token, client)
    except AuthenticationError:
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie(key=settings.cookie_login_token)
        return response

    if calendar_ids:
        selected_calendar_ids = calendar_ids
    else:
        selected_calendar_ids = [str(cal["id"]) for cal in calendars]

    return templates.TemplateResponse(
        "agenda.html",
        {
            "request": request,
            "calendars": calendars,
            "selected_calendar_ids": selected_calendar_ids,
            "start_date": start_date,
            "end_date": end_date,
            "base_url": settings.churchtools_base,
            "version": settings.version,
        },
    )


@router.get("/services")
async def services_page(
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    calendar_ids: Optional[List[str]] = Query(None),
) -> Response:
    """Dienstplan page — shows who does what per event."""
    login_token = request.cookies.get(settings.cookie_login_token)
    if not login_token:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    if not start_date or not end_date:
        start_date_default, end_date_default = get_date_range_from_form()
        start_date = start_date or start_date_default
        end_date = end_date or end_date_default

    try:
        calendars = await fetch_calendars(login_token, client)
    except AuthenticationError:
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie(key=settings.cookie_login_token)
        return response

    if calendar_ids:
        selected_calendar_ids = calendar_ids
    else:
        selected_calendar_ids = [str(cal["id"]) for cal in calendars]

    return templates.TemplateResponse(
        "services.html",
        {
            "request": request,
            "calendars": calendars,
            "selected_calendar_ids": selected_calendar_ids,
            "start_date": start_date,
            "end_date": end_date,
            "base_url": settings.churchtools_base,
            "version": settings.version,
        },
    )


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


@router.get("/api/events/{event_id}/agenda/pdf")
async def api_agenda_pdf(
    request: Request,
    event_id: int,
    event_name: str = Query(...),
    event_start: str = Query(...),
    client: httpx.AsyncClient = Depends(get_http_client),
) -> Response:
    """Generate and download an agenda PDF for a single event."""
    login_token = request.cookies.get(settings.cookie_login_token)
    if not login_token:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)

    try:
        items = await fetch_agenda(login_token, event_id, client)
    except AuthenticationError:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)

    pdf_bytes = create_agenda_pdf(event_name, event_start, items)
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={timestamp}_agenda.pdf"},
    )


@router.get("/api/events/{event_id}/services/pdf")
async def api_event_services_pdf(
    request: Request,
    event_id: int,
    event_name: str = Query(...),
    event_start: str = Query(...),
    client: httpx.AsyncClient = Depends(get_http_client),
    start_date: str = Query(...),
    end_date: str = Query(...),
    calendar_ids: List[str] = Query(...),
) -> Response:
    """Generate and download a services PDF for a single event."""
    login_token = request.cookies.get(settings.cookie_login_token)
    if not login_token:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)

    try:
        events = await fetch_events(login_token, start_date, end_date, calendar_ids, client)
    except AuthenticationError:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)

    # Filter to the requested event
    event = next((ev for ev in events if ev.id == event_id), None)
    if not event:
        return JSONResponse({"error": "Event nicht gefunden"}, status_code=404)

    pdf_bytes = create_services_pdf(event_name, [event])
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={timestamp}_dienstplan.pdf"},
    )
