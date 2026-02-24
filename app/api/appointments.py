import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, File, UploadFile
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import zipfile
from io import BytesIO
from pdf2image import convert_from_path
from datetime import datetime, timedelta
import httpx

from app.database import get_db, save_additional_infos, get_additional_infos, save_color_settings, load_color_settings
from app.config import Config
from app.services.pdf_generator import create_pdf
from app.utils import parse_iso_datetime, normalize_newlines, get_date_range_from_form

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Helper functions
async def fetch_calendars(login_token: str):
    url = f'{Config.CHURCHTOOLS_BASE_URL}/api/calendars'
    headers = {'Authorization': f'Login {login_token}'}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        
        if response.status_code == 200:
            all_calendars = response.json().get('data', [])
            public_calendars = [calendar for calendar in all_calendars if calendar.get('isPublic') is True]
            return public_calendars
        else:
            response.raise_for_status()

async def fetch_appointments(login_token: str, start_date: str, end_date: str, calendar_ids: List[int]):
    headers = {'Authorization': f'Login {login_token}'}
    query_params = {
        'from': start_date,
        'to': end_date,
    }
    appointments = []
    seen_ids = set()  # Set to track seen appointment IDs

    async with httpx.AsyncClient() as client:
        for calendar_id in calendar_ids:
            url = f'{Config.CHURCHTOOLS_BASE_URL}/api/calendars/{calendar_id}/appointments'
            response = await client.get(url, headers=headers, params=query_params)
            
            if response.status_code == 200:
                appointment_counts = {}  # Dictionary to keep track of appointment counts

                for appointment in response.json()['data']:
                    base_id = str(appointment['base']['id'])
                    appointment_id = str(calendar_id) + "_" + base_id

                    # Check if the appointment_id already exists, and increment the count
                    if appointment_id in appointment_counts:
                        appointment_counts[appointment_id] += 1
                        appointment_id += f"_{appointment_counts[appointment_id]}"
                    else:
                        appointment_counts[appointment_id] = 0  # Initialize count for new ID

                    if appointment_id not in seen_ids:
                        seen_ids.add(appointment_id)
                        appointment['base']['id'] = appointment_id
                        appointments.append(appointment)

    appointments.sort(key=lambda x: parse_iso_datetime(x['calculated']['startDate']))
    return appointments

def appointment_to_dict(appointment):
    start_date_from_appointment = appointment['calculated']['startDate']
    start_date_datetime = parse_iso_datetime(start_date_from_appointment)

    end_date_from_appointment = appointment['calculated']['endDate']
    end_date_datetime = parse_iso_datetime(end_date_from_appointment)

    address = appointment['base'].get('address', '')

    if address is not None:
        meeting_at = address.get('meetingAt', '')
    else:
        meeting_at = ''  # Or however you'd like to handle a missing address

    return {
        'id': appointment['base']['id'],
        'description': appointment['base']['caption'],
        'startDate': start_date_from_appointment,
        'endDate': appointment['calculated']['endDate'],
        'address': appointment['base'].get('address', ''),
        'meetingAt': meeting_at,
        'information': appointment['base']['information'],
        'startDateView': start_date_datetime.strftime('%d.%m.%Y'),
        'startTimeView': start_date_datetime.strftime('%H:%M'),
        'endTimeView': end_date_datetime.strftime('%H:%M'),
        'additional_info': ""
    }


def _build_template_context(
    request: Request,
    calendars: list,
    selected_calendar_ids: list,
    start_date: str,
    end_date: str,
    color_settings: dict,
    **extra
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
    color_settings: dict,
    background_image: Optional[UploadFile],
):
    """Shared preparation logic for PDF and JPEG generation.

    Returns (selected_appointments, background_image_stream).
    """
    # Save additional information from form
    form_data = await request.form()
    appointment_info_list = []
    for app_id in appointment_id:
        additional_info = form_data.get(f'additional_info_{app_id}', "")
        normalized_info = normalize_newlines(additional_info)
        appointment_info_list.append((app_id, normalized_info))

    save_additional_infos(db, appointment_info_list)
    save_color_settings(db, color_settings)

    # Process background image
    background_image_stream = None
    if background_image and background_image.filename:
        try:
            content = await background_image.read()
            if content:
                background_image_stream = BytesIO(content)
        except Exception as e:
            logger.error(f"Error reading background image: {e}")

    # Fetch and convert appointments
    logger.info(f"Selected appointment IDs: {appointment_id}")
    logger.info(f"Retrieving appointments for period {start_date} to {end_date} and calendars {calendar_ids_int}")
    appointments_data = await fetch_appointments(login_token, start_date, end_date, calendar_ids_int)
    logger.info(f"Number of retrieved appointments: {len(appointments_data)}")
    appointments = [appointment_to_dict(app) for app in appointments_data]

    # Assign additional info from form
    for appointment in appointments:
        app_id = appointment['id']
        appointment['additional_info'] = form_data.get(f'additional_info_{app_id}', "")

    # Filter selected appointments
    selected_appointments = []
    for app_id in appointment_id:
        matching = [app for app in appointments if str(app['id']) == str(app_id)]
        selected_appointments.extend(matching)

    # Sort by start date
    selected_appointments.sort(key=lambda x: parse_iso_datetime(x['startDate']))

    logger.info(f"Number of selected appointments: {len(selected_appointments)}")
    for idx, app in enumerate(selected_appointments, 1):
        logger.info(f"  {idx}. {app['description']} am {app['startDateView']} ({app['startTimeView']}-{app['endTimeView']})")

    return selected_appointments, background_image_stream


def handle_jpeg_generation(pdf_filename):
    full_pdf_path = os.path.join(Config.FILE_DIRECTORY, pdf_filename)
    images = convert_from_path(full_pdf_path)
    jpeg_files = []

    for i, image in enumerate(images):
        jpeg_stream = BytesIO()
        image.save(jpeg_stream, 'JPEG')
        jpeg_stream.seek(0)
        jpeg_files.append((f'page_{i + 1}.jpg', jpeg_stream))

    zip_filename = os.path.splitext(pdf_filename)[0] + ".zip"
    zip_path = os.path.join(Config.FILE_DIRECTORY, zip_filename)
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file_name, file_bytes in jpeg_files:
            zip_file.writestr(file_name, file_bytes.read())
    
    logger.info(f"JPEG images successfully created and packed into ZIP file: {zip_filename}")
    return zip_filename

@router.get("/appointments")
async def appointments_page(
    request: Request,
    db: Session = Depends(get_db)
):
    login_token = request.cookies.get("login_token")
    if not login_token:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    
    start_date, end_date = get_date_range_from_form()
    calendars = await fetch_calendars(login_token)
    
    # Preselection of all calendars
    selected_calendar_ids = [str(calendar['id']) for calendar in calendars]
    
    # Lade Farbeinstellungen
    color_settings = load_color_settings(db, "default")
    
    return templates.TemplateResponse(
        "appointments.html",
        _build_template_context(request, calendars, selected_calendar_ids, start_date, end_date, color_settings)
    )


async def _handle_fetch_appointments(
    request, db, login_token, calendars, calendar_ids, calendar_ids_int, start_date, end_date
):
    """Handle the 'fetch appointments' button: load appointments and render the template."""
    appointments_data = await fetch_appointments(login_token, start_date, end_date, calendar_ids_int)
    appointments = [appointment_to_dict(app) for app in appointments_data]

    # Load additional information
    additional_infos = get_additional_infos(db, [app['id'] for app in appointments])
    for appointment in appointments:
        appointment['additional_info'] = additional_infos.get(appointment['id'], "")

    # Reload color settings from DB (ignore form overrides for fetch)
    color_settings = load_color_settings(db, "default")

    context = _build_template_context(
        request, calendars, calendar_ids, start_date, end_date, color_settings,
        appointments=appointments,
    )
    response = templates.TemplateResponse("appointments.html", context)
    response.set_cookie(key="fetchAppointments", value="true", max_age=1, path='/')
    return response


async def _handle_generate_pdf(
    request, db, login_token, calendars, calendar_ids, calendar_ids_int,
    start_date, end_date, appointment_id, color_settings, background_image,
):
    """Handle the 'generate PDF' button."""
    if not appointment_id:
        context = _build_template_context(
            request, calendars, calendar_ids, start_date, end_date, color_settings,
            error="Please select at least one appointment.",
        )
        return templates.TemplateResponse("appointments.html", context)

    selected_appointments, bg_stream = await _prepare_selected_appointments(
        request, db, login_token, appointment_id,
        start_date, end_date, calendar_ids_int, color_settings, background_image,
    )

    filename = create_pdf(
        selected_appointments, color_settings['date_color'], color_settings['background_color'],
        color_settings['description_color'], color_settings['background_alpha'], bg_stream,
    )

    response = RedirectResponse(url=f"/download/{filename}", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="pdfGenerated", value="true", max_age=1, path='/')
    return response


async def _handle_generate_jpeg(
    request, db, login_token, calendars, calendar_ids, calendar_ids_int,
    start_date, end_date, appointment_id, color_settings, background_image,
):
    """Handle the 'generate JPEG' button: create PDF, convert to JPEG images, return ZIP."""
    if not appointment_id:
        context = _build_template_context(
            request, calendars, calendar_ids, start_date, end_date, color_settings,
            error="Please select at least one appointment.",
        )
        return templates.TemplateResponse("appointments.html", context)

    selected_appointments, bg_stream = await _prepare_selected_appointments(
        request, db, login_token, appointment_id,
        start_date, end_date, calendar_ids_int, color_settings, background_image,
    )

    filename = create_pdf(
        selected_appointments, color_settings['date_color'], color_settings['background_color'],
        color_settings['description_color'], color_settings['background_alpha'], bg_stream,
    )

    zip_filename = handle_jpeg_generation(filename)

    response = FileResponse(
        os.path.join(Config.FILE_DIRECTORY, zip_filename),
        media_type="application/zip",
        filename=zip_filename,
    )
    response.set_cookie(key="jpegGenerated", value="true", max_age=1, path='/')
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
    background_image: Optional[UploadFile] = File(None),
    date_color: Optional[str] = Form(None),
    description_color: Optional[str] = Form(None),
    background_color: Optional[str] = Form(None),
    alpha: Optional[int] = Form(None)
):
    login_token = request.cookies.get("login_token")
    if not login_token:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    # Default values for date range if not in the form
    if not start_date or not end_date:
        start_date_default, end_date_default = get_date_range_from_form()
        start_date = start_date or start_date_default
        end_date = end_date or end_date_default

    calendars = await fetch_calendars(login_token)

    # Convert calendar_ids to integers if available
    calendar_ids_int = []
    if calendar_ids:
        calendar_ids_int = [int(id) for id in calendar_ids if id.isdigit()]

    # If no calendars are selected, use all available calendars
    if not calendar_ids_int and calendars:
        calendar_ids_int = [calendar['id'] for calendar in calendars]
        logger.info(f"No calendars selected, using all available calendars: {calendar_ids_int}")

    # Load color settings with form overrides
    color_settings = load_color_settings(db, "default")
    if background_color:
        color_settings['background_color'] = background_color
    if alpha is not None:
        color_settings['background_alpha'] = alpha
    if date_color:
        color_settings['date_color'] = date_color
    if description_color:
        color_settings['description_color'] = description_color

    # Dispatch to the appropriate handler
    if fetch_appointments_btn:
        return await _handle_fetch_appointments(
            request, db, login_token, calendars, calendar_ids, calendar_ids_int, start_date, end_date,
        )

    if generate_pdf_btn:
        return await _handle_generate_pdf(
            request, db, login_token, calendars, calendar_ids, calendar_ids_int,
            start_date, end_date, appointment_id, color_settings, background_image,
        )

    if generate_jpeg_btn:
        return await _handle_generate_jpeg(
            request, db, login_token, calendars, calendar_ids, calendar_ids_int,
            start_date, end_date, appointment_id, color_settings, background_image,
        )

    # Default: show form
    context = _build_template_context(
        request, calendars, calendar_ids, start_date, end_date, color_settings,
    )
    return templates.TemplateResponse("appointments.html", context)

@router.get("/download/{filename}")
async def download_file(filename: str):
    file_path = os.path.join(Config.FILE_DIRECTORY, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(file_path, filename=filename)