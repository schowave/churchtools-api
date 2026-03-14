import logging
import os
from io import BytesIO
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.config import Config
from app.crud import (
    delete_background_image,
    delete_logo,
    get_additional_infos,
    load_background_image,
    load_color_settings,
    load_logo,
    save_additional_infos,
    save_background_image,
    save_color_settings,
    save_logo,
)
from app.database import DEFAULT_SETTING_NAME, get_db
from app.schemas import ColorSettings, GenerateRequest
from app.services.churchtools_client import AuthenticationError, fetch_appointments, fetch_calendars, parse_appointment
from app.services.jpeg_generator import handle_jpeg_generation
from app.services.pdf_generator import create_pdf
from app.shared import templates
from app.utils import get_date_range_from_form, normalize_newlines

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB


def _require_auth(request: Request):
    """Raise 401 if no login token is present."""
    if not request.cookies.get(Config.COOKIE_LOGIN_TOKEN):
        raise HTTPException(status_code=401, detail="Nicht angemeldet")


logger = logging.getLogger(__name__)

router = APIRouter()


def _build_template_context(
    request: Request,
    calendars: list,
    selected_calendar_ids: list,
    start_date: str,
    end_date: str,
    color_settings: ColorSettings,
    has_logo: bool = False,
    has_background_image: bool = False,
    **extra,
) -> dict:
    """Build the common template context dict for appointments.html."""
    context = {
        "request": request,
        "calendars": calendars,
        "selected_calendar_ids": selected_calendar_ids,
        "start_date": start_date,
        "end_date": end_date,
        "base_url": Config.CHURCHTOOLS_BASE,
        "color_settings": color_settings,
        "has_logo": has_logo,
        "has_background_image": has_background_image,
        "version": Config.VERSION,
    }
    context.update(extra)
    return context


@router.get("/appointments")
async def appointments_page(
    request: Request,
    db: Session = Depends(get_db),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    calendar_ids: Optional[List[str]] = Query(None),
):
    login_token = request.cookies.get(Config.COOKIE_LOGIN_TOKEN)
    if not login_token:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    if not start_date or not end_date:
        start_date_default, end_date_default = get_date_range_from_form()
        start_date = start_date or start_date_default
        end_date = end_date or end_date_default

    try:
        calendars = await fetch_calendars(login_token)
    except AuthenticationError:
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie(key=Config.COOKIE_LOGIN_TOKEN)
        return response

    # Use provided calendar_ids or preselect all
    if calendar_ids:
        selected_calendar_ids = calendar_ids
    else:
        selected_calendar_ids = [str(calendar["id"]) for calendar in calendars]

    color_settings = load_color_settings(db, DEFAULT_SETTING_NAME)
    logo_data, _ = load_logo(db, DEFAULT_SETTING_NAME)
    has_logo = logo_data is not None
    bg_data, _ = load_background_image(db, DEFAULT_SETTING_NAME)
    has_background_image = bg_data is not None

    return templates.TemplateResponse(
        "appointments.html",
        _build_template_context(
            request,
            calendars,
            selected_calendar_ids,
            start_date,
            end_date,
            color_settings,
            has_logo=has_logo,
            has_background_image=has_background_image,
        ),
    )


@router.get("/api/appointments")
async def api_appointments(
    request: Request,
    db: Session = Depends(get_db),
    start_date: str = Query(...),
    end_date: str = Query(...),
    calendar_ids: List[str] = Query(...),
):
    """JSON endpoint for async appointment loading."""
    login_token = request.cookies.get(Config.COOKIE_LOGIN_TOKEN)
    if not login_token:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)

    calendar_ids_int = [int(cid) for cid in calendar_ids if cid.isdigit()]
    if not calendar_ids_int:
        return JSONResponse({"appointments": []})

    try:
        raw_appointments = await fetch_appointments(login_token, start_date, end_date, calendar_ids_int)
    except AuthenticationError:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)

    appointments = [parse_appointment(raw) for raw in raw_appointments]
    additional_infos = get_additional_infos(db, [app.id for app in appointments])
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
):
    """JSON endpoint for PDF/JPEG generation."""
    login_token = request.cookies.get(Config.COOKIE_LOGIN_TOKEN)
    if not login_token:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)

    color_settings = body.color_settings

    # Save additional infos to DB
    appointment_info_list = [
        (app_id, normalize_newlines(body.additional_infos.get(app_id, ""))) for app_id in body.appointment_ids
    ]
    save_additional_infos(db, appointment_info_list)
    save_color_settings(db, color_settings)

    # Load background image and logo from DB
    background_image_stream = None
    bg_data, _ = load_background_image(db, DEFAULT_SETTING_NAME)
    if bg_data:
        background_image_stream = BytesIO(bg_data)

    logo_stream = None
    logo_data, _ = load_logo(db, DEFAULT_SETTING_NAME)
    if logo_data:
        logo_stream = BytesIO(logo_data)

    # Fetch appointments from ChurchTools API
    calendar_ids_int = [int(cid) for cid in body.calendar_ids if cid.isdigit()]
    try:
        raw_appointments = await fetch_appointments(login_token, body.start_date, body.end_date, calendar_ids_int)
    except AuthenticationError:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)

    appointments = [parse_appointment(raw) for raw in raw_appointments]

    # Assign additional info from request body
    for appointment in appointments:
        appointment.additional_info = body.additional_infos.get(appointment.id, "")

    # Filter to selected appointments
    selected_ids = set(body.appointment_ids)
    selected_appointments = [app for app in appointments if app.id in selected_ids]

    # Preserve order from request
    id_order = {app_id: idx for idx, app_id in enumerate(body.appointment_ids)}
    selected_appointments.sort(key=lambda app: id_order.get(app.id, 0))

    logger.info(f"Generating {body.type}: {len(selected_appointments)} of {len(appointments)} appointments")

    # Generate PDF
    filename = create_pdf(
        selected_appointments,
        color_settings.date_color,
        color_settings.background_color,
        color_settings.description_color,
        color_settings.background_alpha,
        background_image_stream,
        logo_stream,
    )

    # Convert to JPEG if requested
    if body.type == "jpeg":
        filename = handle_jpeg_generation(filename)

    return JSONResponse({"download_url": f"/download/{filename}"})


@router.post("/logo/upload")
async def upload_logo(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a logo image and store it in the database."""
    _require_auth(request)
    content = await file.read(MAX_UPLOAD_SIZE + 1)
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="Datei zu groß (max. 10 MB)")
    if not content:
        raise HTTPException(status_code=400, detail="Leere Datei")
    save_logo(db, DEFAULT_SETTING_NAME, content, file.filename)
    return JSONResponse({"status": "ok", "filename": file.filename})


@router.get("/logo")
async def get_logo(db: Session = Depends(get_db)):
    """Serve the stored logo image for preview."""
    logo_data, logo_filename = load_logo(db, DEFAULT_SETTING_NAME)
    if not logo_data:
        raise HTTPException(status_code=404, detail="Kein Logo gespeichert")

    ext = (logo_filename.rsplit(".", 1)[-1] if "." in logo_filename else "png").lower()
    media_types = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "svg": "image/svg+xml"}
    media_type = media_types.get(ext, "image/png")

    return Response(content=logo_data, media_type=media_type)


@router.delete("/logo")
async def remove_logo(request: Request, db: Session = Depends(get_db)):
    """Delete the stored logo."""
    _require_auth(request)
    delete_logo(db, DEFAULT_SETTING_NAME)
    return JSONResponse({"status": "ok"})


@router.post("/background/upload")
async def upload_background(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a background image and store it in the database."""
    _require_auth(request)
    content = await file.read(MAX_UPLOAD_SIZE + 1)
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="Datei zu groß (max. 10 MB)")
    if not content:
        raise HTTPException(status_code=400, detail="Leere Datei")
    save_background_image(db, DEFAULT_SETTING_NAME, content, file.filename)
    return JSONResponse({"status": "ok", "filename": file.filename})


@router.get("/background")
async def get_background(db: Session = Depends(get_db)):
    """Serve the stored background image for preview."""
    image_data, image_filename = load_background_image(db, DEFAULT_SETTING_NAME)
    if not image_data:
        raise HTTPException(status_code=404, detail="Kein Hintergrundbild gespeichert")

    ext = (image_filename.rsplit(".", 1)[-1] if "." in image_filename else "png").lower()
    media_types = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "svg": "image/svg+xml"}
    media_type = media_types.get(ext, "image/png")

    return Response(content=image_data, media_type=media_type)


@router.delete("/background")
async def remove_background(request: Request, db: Session = Depends(get_db)):
    """Delete the stored background image."""
    _require_auth(request)
    delete_background_image(db, DEFAULT_SETTING_NAME)
    return JSONResponse({"status": "ok"})


@router.get("/download/{filename}")
async def download_file(filename: str):
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(Config.FILE_DIRECTORY, safe_filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        file_path,
        filename=safe_filename,
        headers={"Cache-Control": "no-store"},
    )
