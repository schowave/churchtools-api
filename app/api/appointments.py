from collections.abc import Callable
from io import BytesIO

import httpx
import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response, StreamingResponse
from PIL import Image
from sqlalchemy.orm import Session

from app.api.calendar_pages import render_calendar_page
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
from app.dependencies import get_http_client
from app.schemas import GenerateRequest
from app.services.auth import get_valid_login_token
from app.services.churchtools_client import AuthenticationError, fetch_appointments, parse_appointment
from app.services.jpeg_generator import handle_jpeg_generation
from app.services.pdf_generator import create_pdf
from app.utils import export_timestamp, normalize_newlines

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_IMAGE_PIXELS = 40_000_000  # guards against decompression bombs
IMAGE_FORMATS = {"PNG", "JPEG"}


async def _require_auth(request: Request, client: httpx.AsyncClient) -> None:
    """Raise 401 unless ChurchTools accepts the login token."""
    if not await get_valid_login_token(request, client):
        raise HTTPException(status_code=401, detail="Nicht angemeldet")


async def _read_image_upload(file: UploadFile) -> bytes:
    """Read an uploaded file and reject anything that is not a sane PNG or JPEG."""
    content = await file.read(MAX_UPLOAD_SIZE + 1)
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="Datei zu groß (max. 10 MB)")
    if not content:
        raise HTTPException(status_code=400, detail="Leere Datei")
    try:
        with Image.open(BytesIO(content)) as image:
            image_format = image.format
            width, height = image.size
            image.verify()
    except Exception:
        raise HTTPException(status_code=400, detail="Nur PNG- oder JPEG-Bilder erlaubt") from None
    if image_format not in IMAGE_FORMATS:
        raise HTTPException(status_code=400, detail="Nur PNG- oder JPEG-Bilder erlaubt")
    if width * height > MAX_IMAGE_PIXELS:
        raise HTTPException(status_code=413, detail="Bild zu groß (max. 40 Megapixel)")
    return content


def _image_response(data: bytes, not_found_detail: str) -> Response:
    """Serve stored image bytes with a content type derived from the data, never from the filename."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        media_type = "image/png"
    elif data.startswith(b"\xff\xd8\xff"):
        media_type = "image/jpeg"
    else:
        # Legacy uploads (e.g. SVG) from before upload validation are not served.
        raise HTTPException(status_code=404, detail=not_found_detail)
    return Response(content=data, media_type=media_type, headers={"Content-Security-Policy": "default-src 'none'"})


logger = structlog.get_logger()

router = APIRouter()


@router.get("/appointments")
async def appointments_page(
    request: Request,
    db: Session = Depends(get_db),
    client: httpx.AsyncClient = Depends(get_http_client),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    calendar_ids: list[str] | None = Query(None),
) -> Response:
    def styling_context() -> dict:
        logo_data, _ = load_logo(db, DEFAULT_SETTING_NAME)
        bg_data, _ = load_background_image(db, DEFAULT_SETTING_NAME)
        return {
            "color_settings": load_color_settings(db, DEFAULT_SETTING_NAME),
            "has_logo": logo_data is not None,
            "has_background_image": bg_data is not None,
        }

    return await render_calendar_page(
        request, client, "appointments.html", start_date, end_date, calendar_ids, styling_context
    )


@router.get("/api/appointments")
async def api_appointments(
    request: Request,
    db: Session = Depends(get_db),
    client: httpx.AsyncClient = Depends(get_http_client),
    start_date: str = Query(...),
    end_date: str = Query(...),
    calendar_ids: list[str] = Query(...),
) -> JSONResponse:
    """JSON endpoint for async appointment loading."""
    login_token = await get_valid_login_token(request, client)
    if not login_token:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)

    calendar_ids_int = [int(cid) for cid in calendar_ids if cid.isdigit()]
    if not calendar_ids_int:
        return JSONResponse({"appointments": []})

    try:
        raw_appointments = await fetch_appointments(login_token, start_date, end_date, calendar_ids_int, client)
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
    client: httpx.AsyncClient = Depends(get_http_client),
) -> Response:
    """JSON endpoint for PDF/JPEG generation."""
    login_token = await get_valid_login_token(request, client)
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
    bg_data, _ = load_background_image(db, body.profile)
    if bg_data:
        background_image_stream = BytesIO(bg_data)

    logo_stream = None
    logo_data, _ = load_logo(db, body.profile)
    if logo_data:
        logo_stream = BytesIO(logo_data)

    # Fetch appointments from ChurchTools API
    calendar_ids_int = [int(cid) for cid in body.calendar_ids if cid.isdigit()]
    try:
        raw_appointments = await fetch_appointments(
            login_token, body.start_date, body.end_date, calendar_ids_int, client
        )
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


async def _upload_image(request, file, client, save: Callable[[bytes, str], None]) -> JSONResponse:
    await _require_auth(request, client)
    content = await _read_image_upload(file)
    save(content, file.filename)
    return JSONResponse({"status": "ok", "filename": file.filename})


async def _serve_image(request, client, load: Callable[[], tuple], missing_detail: str) -> Response:
    await _require_auth(request, client)
    data, _ = load()
    if not data:
        raise HTTPException(status_code=404, detail=missing_detail)
    return _image_response(data, missing_detail)


async def _remove_image(request, client, delete: Callable[[], None]) -> JSONResponse:
    await _require_auth(request, client)
    delete()
    return JSONResponse({"status": "ok"})


@router.post("/logo/upload")
async def upload_logo(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    client: httpx.AsyncClient = Depends(get_http_client),
) -> JSONResponse:
    """Upload a logo image and store it in the database."""
    return await _upload_image(
        request, file, client, lambda data, name: save_logo(db, DEFAULT_SETTING_NAME, data, name)
    )


@router.get("/logo")
async def get_logo(
    request: Request, db: Session = Depends(get_db), client: httpx.AsyncClient = Depends(get_http_client)
) -> Response:
    """Serve the stored logo image for preview."""
    return await _serve_image(request, client, lambda: load_logo(db, DEFAULT_SETTING_NAME), "Kein Logo gespeichert")


@router.delete("/logo")
async def remove_logo(
    request: Request, db: Session = Depends(get_db), client: httpx.AsyncClient = Depends(get_http_client)
) -> JSONResponse:
    """Delete the stored logo."""
    return await _remove_image(request, client, lambda: delete_logo(db, DEFAULT_SETTING_NAME))


@router.post("/background/upload")
async def upload_background(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    client: httpx.AsyncClient = Depends(get_http_client),
) -> JSONResponse:
    """Upload a background image and store it in the database."""
    return await _upload_image(
        request, file, client, lambda data, name: save_background_image(db, DEFAULT_SETTING_NAME, data, name)
    )


@router.get("/background")
async def get_background(
    request: Request, db: Session = Depends(get_db), client: httpx.AsyncClient = Depends(get_http_client)
) -> Response:
    """Serve the stored background image for preview."""
    return await _serve_image(
        request, client, lambda: load_background_image(db, DEFAULT_SETTING_NAME), "Kein Hintergrundbild gespeichert"
    )


@router.delete("/background")
async def remove_background(
    request: Request, db: Session = Depends(get_db), client: httpx.AsyncClient = Depends(get_http_client)
) -> JSONResponse:
    """Delete the stored background image."""
    return await _remove_image(request, client, lambda: delete_background_image(db, DEFAULT_SETTING_NAME))
