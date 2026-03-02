import logging
import os
from io import BytesIO
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
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
from app.schemas import ColorSettings
from app.services.churchtools_client import AuthenticationError, fetch_appointments, fetch_calendars, parse_appointment
from app.services.jpeg_generator import handle_jpeg_generation
from app.services.pdf_generator import create_pdf
from app.shared import templates
from app.utils import get_date_range_from_form, normalize_newlines

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


async def _prepare_selected_appointments(
    request: Request,
    db: Session,
    login_token: str,
    appointment_id: List[str],
    start_date: str,
    end_date: str,
    calendar_ids_int: List[int],
    color_settings: ColorSettings,
):
    """Shared preparation logic for PDF and JPEG generation.

    Returns (selected_appointments: List[AppointmentData], background_image_stream, logo_stream).
    """
    # Save additional information from form
    form_data = await request.form()
    appointment_info_list = []
    for app_id in appointment_id:
        additional_info = form_data.get(f"additional_info_{app_id}", "")
        normalized_info = normalize_newlines(additional_info)
        appointment_info_list.append((app_id, normalized_info))

    save_additional_infos(db, appointment_info_list)
    save_color_settings(db, color_settings)

    # Load background image from DB
    background_image_stream = None
    bg_data, _ = load_background_image(db, DEFAULT_SETTING_NAME)
    if bg_data:
        background_image_stream = BytesIO(bg_data)

    # Load logo from DB
    logo_stream = None
    logo_data, _ = load_logo(db, DEFAULT_SETTING_NAME)
    if logo_data:
        logo_stream = BytesIO(logo_data)

    # Fetch and convert appointments
    logger.info(f"Selected appointment IDs: {appointment_id}")
    logger.info(f"Retrieving appointments for period {start_date} to {end_date} and calendars {calendar_ids_int}")
    raw_appointments = await fetch_appointments(login_token, start_date, end_date, calendar_ids_int)
    logger.info(f"Number of retrieved appointments: {len(raw_appointments)}")
    appointments = [parse_appointment(raw) for raw in raw_appointments]

    # Assign additional info from form
    for appointment in appointments:
        info = form_data.get(f"additional_info_{appointment.id}", "")
        appointment.additional_info = info

    # Filter selected appointments
    selected_ids = set(appointment_id)
    selected_appointments = [app for app in appointments if app.id in selected_ids]

    # Preserve order from appointment_id list
    id_order = {app_id: idx for idx, app_id in enumerate(appointment_id)}
    selected_appointments.sort(key=lambda app: id_order.get(app.id, 0))

    logger.info(f"Number of selected appointments: {len(selected_appointments)}")
    for idx, app in enumerate(selected_appointments, 1):
        logger.info(f"  {idx}. {app.title} am {app.start_date_view} ({app.start_time_view}-{app.end_time_view})")

    return selected_appointments, background_image_stream, logo_stream


@router.get("/appointments")
async def appointments_page(request: Request, db: Session = Depends(get_db)):
    login_token = request.cookies.get(Config.COOKIE_LOGIN_TOKEN)
    if not login_token:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    start_date, end_date = get_date_range_from_form()
    try:
        calendars = await fetch_calendars(login_token)
    except AuthenticationError:
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie(key=Config.COOKIE_LOGIN_TOKEN)
        return response

    # Preselection of all calendars
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


async def _handle_fetch_appointments(
    request, db, login_token, calendars, calendar_ids, calendar_ids_int, start_date, end_date
):
    """Handle the 'fetch appointments' button: load appointments and render the template."""
    raw_appointments = await fetch_appointments(login_token, start_date, end_date, calendar_ids_int)
    appointments = [parse_appointment(raw) for raw in raw_appointments]

    # Load additional information from DB
    additional_infos = get_additional_infos(db, [app.id for app in appointments])
    for appointment in appointments:
        appointment.additional_info = additional_infos.get(appointment.id, "")

    # Reload color settings from DB (ignore form overrides for fetch)
    color_settings = load_color_settings(db, DEFAULT_SETTING_NAME)
    logo_data, _ = load_logo(db, DEFAULT_SETTING_NAME)
    bg_data, _ = load_background_image(db, DEFAULT_SETTING_NAME)

    context = _build_template_context(
        request,
        calendars,
        calendar_ids,
        start_date,
        end_date,
        color_settings,
        has_logo=logo_data is not None,
        has_background_image=bg_data is not None,
        appointments=appointments,
    )
    response = templates.TemplateResponse("appointments.html", context)
    response.set_cookie(key="fetchAppointments", value="true", max_age=1, path="/")
    return response


async def _handle_generate_pdf(
    request,
    db,
    login_token,
    calendars,
    calendar_ids,
    calendar_ids_int,
    start_date,
    end_date,
    appointment_id,
    color_settings,
):
    """Handle the 'generate PDF' button."""
    if not appointment_id:
        context = _build_template_context(
            request,
            calendars,
            calendar_ids,
            start_date,
            end_date,
            color_settings,
            error="Bitte mindestens einen Termin auswählen.",
        )
        return templates.TemplateResponse("appointments.html", context)

    selected_appointments, bg_stream, logo_stream = await _prepare_selected_appointments(
        request,
        db,
        login_token,
        appointment_id,
        start_date,
        end_date,
        calendar_ids_int,
        color_settings,
    )

    filename = create_pdf(
        selected_appointments,
        color_settings.date_color,
        color_settings.background_color,
        color_settings.description_color,
        color_settings.background_alpha,
        bg_stream,
        logo_stream,
    )

    response = RedirectResponse(url=f"/download/{filename}", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="pdfGenerated", value="true", max_age=1, path="/")
    return response


async def _handle_generate_jpeg(
    request,
    db,
    login_token,
    calendars,
    calendar_ids,
    calendar_ids_int,
    start_date,
    end_date,
    appointment_id,
    color_settings,
):
    """Handle the 'generate JPEG' button: create PDF, convert to JPEG images, return ZIP."""
    if not appointment_id:
        context = _build_template_context(
            request,
            calendars,
            calendar_ids,
            start_date,
            end_date,
            color_settings,
            error="Bitte mindestens einen Termin auswählen.",
        )
        return templates.TemplateResponse("appointments.html", context)

    selected_appointments, bg_stream, logo_stream = await _prepare_selected_appointments(
        request,
        db,
        login_token,
        appointment_id,
        start_date,
        end_date,
        calendar_ids_int,
        color_settings,
    )

    filename = create_pdf(
        selected_appointments,
        color_settings.date_color,
        color_settings.background_color,
        color_settings.description_color,
        color_settings.background_alpha,
        bg_stream,
        logo_stream,
    )

    zip_filename = handle_jpeg_generation(filename)

    response = FileResponse(
        os.path.join(Config.FILE_DIRECTORY, zip_filename),
        media_type="application/zip",
        filename=zip_filename,
    )
    response.set_cookie(key="jpegGenerated", value="true", max_age=1, path="/")
    return response


@router.post("/appointments")
async def process_appointments(
    request: Request,
    db: Session = Depends(get_db),
    fetch_appointments_btn: Optional[str] = Form(None, alias="fetch_appointments"),
    generate_pdf_btn: Optional[str] = Form(None, alias="generate_pdf"),
    generate_jpeg_btn: Optional[str] = Form(None, alias="generate_jpeg"),
    start_date: Optional[str] = Form(None),
    end_date: Optional[str] = Form(None),
    calendar_ids: Optional[List[str]] = Form(None),
    appointment_id: Optional[List[str]] = Form(None),
    date_color: Optional[str] = Form(None),
    description_color: Optional[str] = Form(None),
    background_color: Optional[str] = Form(None),
    alpha: Optional[int] = Form(None),
):
    login_token = request.cookies.get(Config.COOKIE_LOGIN_TOKEN)
    if not login_token:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    # Default values for date range if not in the form
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

    # Convert calendar_ids to integers if available
    calendar_ids_int = []
    if calendar_ids:
        calendar_ids_int = [int(id) for id in calendar_ids if id.isdigit()]

    # If no calendars are selected, use all available calendars
    if not calendar_ids_int and calendars:
        calendar_ids_int = [calendar["id"] for calendar in calendars]
        logger.info(f"No calendars selected, using all available calendars: {calendar_ids_int}")

    # Load color settings with form overrides
    color_settings = load_color_settings(db, DEFAULT_SETTING_NAME)
    overrides = {}
    if background_color:
        overrides["background_color"] = background_color
    if alpha is not None:
        overrides["background_alpha"] = alpha
    if date_color:
        overrides["date_color"] = date_color
    if description_color:
        overrides["description_color"] = description_color
    if overrides:
        color_settings = color_settings.model_copy(update=overrides)

    # Dispatch to the appropriate handler.
    # All handlers call fetch_appointments which may raise AuthenticationError
    # if the token expires mid-session.
    try:
        if fetch_appointments_btn:
            return await _handle_fetch_appointments(
                request,
                db,
                login_token,
                calendars,
                calendar_ids,
                calendar_ids_int,
                start_date,
                end_date,
            )

        if generate_pdf_btn:
            return await _handle_generate_pdf(
                request,
                db,
                login_token,
                calendars,
                calendar_ids,
                calendar_ids_int,
                start_date,
                end_date,
                appointment_id,
                color_settings,
            )

        if generate_jpeg_btn:
            return await _handle_generate_jpeg(
                request,
                db,
                login_token,
                calendars,
                calendar_ids,
                calendar_ids_int,
                start_date,
                end_date,
                appointment_id,
                color_settings,
            )
    except AuthenticationError:
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie(key=Config.COOKIE_LOGIN_TOKEN)
        return response

    # Default: show form
    logo_data, _ = load_logo(db, DEFAULT_SETTING_NAME)
    bg_data, _ = load_background_image(db, DEFAULT_SETTING_NAME)
    context = _build_template_context(
        request,
        calendars,
        calendar_ids,
        start_date,
        end_date,
        color_settings,
        has_logo=logo_data is not None,
        has_background_image=bg_data is not None,
    )
    return templates.TemplateResponse("appointments.html", context)


@router.post("/logo/upload")
async def upload_logo(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a logo image and store it in the database."""
    content = await file.read()
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
async def remove_logo(db: Session = Depends(get_db)):
    """Delete the stored logo."""
    delete_logo(db, DEFAULT_SETTING_NAME)
    return JSONResponse({"status": "ok"})


@router.post("/background/upload")
async def upload_background(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a background image and store it in the database."""
    content = await file.read()
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
async def remove_background(db: Session = Depends(get_db)):
    """Delete the stored background image."""
    delete_background_image(db, DEFAULT_SETTING_NAME)
    return JSONResponse({"status": "ok"})


@router.get("/download/{filename}")
async def download_file(filename: str):
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(Config.FILE_DIRECTORY, safe_filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path, filename=safe_filename)
