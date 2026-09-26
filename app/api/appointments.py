from io import BytesIO

import httpx2
import structlog
from fastapi import APIRouter, Depends, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy.orm import Session

from app.api.calendar_pages import render_calendar_page
from app.crud import (
    claim_legacy_additional_infos,
    get_additional_infos,
    load_background_image,
    load_color_settings,
    load_logo,
    save_additional_infos,
    save_color_settings,
)
from app.database import DEFAULT_SETTING_NAME, get_db
from app.dates import export_timestamp
from app.schemas import ColorSettings, GenerateRequest
from app.services.auth import get_valid_login_token
from app.services.churchtools_client import (
    AuthenticationError,
    fetch_appointments,
    legacy_appointment_ids,
    parse_appointment,
)
from app.services.jpeg_generator import handle_jpeg_generation
from app.services.pdf.slides import create_pdf
from app.text import normalize_newlines
from app.web import check_range_query, get_http_client

logger = structlog.get_logger()

router = APIRouter()


@router.get("/appointments")
async def appointments_page(
    request: Request,
    db: Session = Depends(get_db),
    client: httpx2.AsyncClient = Depends(get_http_client),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    calendar_ids: list[str] | None = Query(None),
) -> Response:
    def styling_context() -> dict:
        logo_data, _ = load_logo(db, DEFAULT_SETTING_NAME)
        bg_data, _ = load_background_image(db, DEFAULT_SETTING_NAME)
        color_settings = load_color_settings(db, DEFAULT_SETTING_NAME)
        has_logo = logo_data is not None
        has_background_image = bg_data is not None
        return {
            "color_settings": color_settings,
            "has_logo": has_logo,
            "has_background_image": has_background_image,
            # First-time users see the design section open; once customised it stays out of the way
            "design_open": color_settings == ColorSettings(name=DEFAULT_SETTING_NAME)
            and not has_logo
            and not has_background_image,
        }

    return await render_calendar_page(
        request, client, "appointments.html", start_date, end_date, calendar_ids, styling_context
    )


@router.get("/api/appointments")
async def api_appointments(
    request: Request,
    db: Session = Depends(get_db),
    client: httpx2.AsyncClient = Depends(get_http_client),
    start_date: str = Query(...),
    end_date: str = Query(...),
    calendar_ids: list[str] = Query(...),
) -> JSONResponse:
    """JSON endpoint for async appointment loading."""
    login_token = await get_valid_login_token(request, client)
    if not login_token:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)
    check_range_query(start_date, end_date, calendar_ids)

    calendar_ids_int = [int(cid) for cid in calendar_ids if cid.isdigit()]
    if not calendar_ids_int:
        return JSONResponse({"appointments": []})

    try:
        raw_appointments = await fetch_appointments(login_token, start_date, end_date, calendar_ids_int, client)
    except AuthenticationError:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)

    appointments = [parse_appointment(raw) for raw in raw_appointments]
    appointment_ids = [app.id for app in appointments]

    def load_additional_infos() -> dict[str, str]:
        infos = get_additional_infos(db, appointment_ids)
        # Texts saved before v7.1 are stored under the old, range-dependent ids
        missing = {new: old for new, old in legacy_appointment_ids(appointment_ids).items() if new not in infos}
        infos.update(claim_legacy_additional_infos(db, missing))
        return infos

    additional_infos = await run_in_threadpool(load_additional_infos)
    for appointment in appointments:
        appointment.additional_info = additional_infos.get(appointment.id, "")

    return JSONResponse(
        {
            "appointments": [app.model_dump() for app in appointments],
        }
    )


@router.post("/api/generate")
async def api_generate(
    request: Request,
    body: GenerateRequest,
    db: Session = Depends(get_db),
    client: httpx2.AsyncClient = Depends(get_http_client),
) -> Response:
    """JSON endpoint for PDF/JPEG generation."""
    login_token = await get_valid_login_token(request, client)
    if not login_token:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)

    # Fetch first: only texts for appointments this user can load from ChurchTools get stored
    calendar_ids_int = [int(cid) for cid in body.calendar_ids if cid.isdigit()]
    try:
        raw_appointments = await fetch_appointments(
            login_token, body.start_date, body.end_date, calendar_ids_int, client
        )
    except AuthenticationError:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)

    appointments = [parse_appointment(raw) for raw in raw_appointments]
    known_ids = {app.id for app in appointments}

    # There is one shared style; a client-supplied name would create extra settings rows
    color_settings = body.color_settings.model_copy(update={"name": DEFAULT_SETTING_NAME})
    appointment_info_list = [
        (app_id, normalize_newlines(body.additional_infos.get(app_id, "")))
        for app_id in body.appointment_ids
        if app_id in known_ids
    ]

    def save_and_load_images() -> tuple[bytes | None, bytes | None]:
        save_additional_infos(db, appointment_info_list)
        save_color_settings(db, color_settings)
        bg_data, _ = load_background_image(db, DEFAULT_SETTING_NAME)
        logo_data, _ = load_logo(db, DEFAULT_SETTING_NAME)
        return bg_data, logo_data

    # Sync DB access stays off the event loop
    bg_data, logo_data = await run_in_threadpool(save_and_load_images)
    background_image_stream = BytesIO(bg_data) if bg_data else None
    logo_stream = BytesIO(logo_data) if logo_data else None

    # Assign additional info from request body
    for appointment in appointments:
        appointment.additional_info = body.additional_infos.get(appointment.id, "")

    # Filter to selected appointments
    selected_ids = set(body.appointment_ids)
    selected_appointments = [app for app in appointments if app.id in selected_ids]

    # Preserve order from request
    id_order = {app_id: idx for idx, app_id in enumerate(body.appointment_ids)}
    selected_appointments.sort(key=lambda app: id_order.get(app.id, 0))

    logger.info("generating_output", type=body.type, selected=len(selected_appointments), available=len(appointments))

    # PDF/JPEG rendering is CPU-bound (and pdftoppm for JPEG): keep it off the event loop
    pdf_bytes = await run_in_threadpool(
        create_pdf,
        selected_appointments,
        color_settings.date_color,
        color_settings.background_color,
        color_settings.description_color,
        color_settings.background_alpha,
        background_image_stream,
        logo_stream,
    )

    timestamp = export_timestamp()

    if body.type == "jpeg":
        zip_bytes = await run_in_threadpool(handle_jpeg_generation, pdf_bytes)
        return StreamingResponse(
            BytesIO(zip_bytes),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={timestamp}_appointments.zip"},
        )

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={timestamp}_appointments.pdf"},
    )
