from io import BytesIO

import httpx
import structlog
from fastapi import APIRouter, Depends, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response, StreamingResponse

from app.api.calendar_pages import render_calendar_page
from app.dependencies import get_http_client
from app.services.auth import get_valid_login_token
from app.services.churchtools_client import (
    AuthenticationError,
    fetch_agenda,
    fetch_events,
)
from app.services.pdf_generator import create_agenda_pdf, create_services_pdf
from app.utils import export_timestamp

logger = structlog.get_logger()
router = APIRouter()


@router.get("/agenda")
async def agenda_page(
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    calendar_ids: list[str] | None = Query(None),
) -> Response:
    """Agenda page — shows worship service rundowns."""
    return await render_calendar_page(request, client, "agenda.html", start_date, end_date, calendar_ids)


@router.get("/services")
async def services_page(
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    calendar_ids: list[str] | None = Query(None),
) -> Response:
    """Dienstplan page — shows who does what per event."""
    return await render_calendar_page(request, client, "services.html", start_date, end_date, calendar_ids)


@router.get("/api/events")
async def api_events(
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
    start_date: str = Query(...),
    end_date: str = Query(...),
    calendar_ids: list[str] = Query(...),
) -> JSONResponse:
    """JSON endpoint returning events with their service assignments."""
    login_token = await get_valid_login_token(request, client)
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
    login_token = await get_valid_login_token(request, client)
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
    login_token = await get_valid_login_token(request, client)
    if not login_token:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)

    try:
        items = await fetch_agenda(login_token, event_id, client)
    except AuthenticationError:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)

    pdf_bytes = await run_in_threadpool(create_agenda_pdf, event_name, event_start, items)
    timestamp = export_timestamp()

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
    calendar_ids: list[str] = Query(...),
) -> Response:
    """Generate and download a services PDF for a single event."""
    login_token = await get_valid_login_token(request, client)
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

    pdf_bytes = await run_in_threadpool(create_services_pdf, event_name, [event])
    timestamp = export_timestamp()

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={timestamp}_dienstplan.pdf"},
    )
