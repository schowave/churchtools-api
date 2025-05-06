import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, File, UploadFile, Cookie
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
import os
import zipfile
from io import BytesIO
from pdf2image import convert_from_path
from datetime import datetime, timedelta

from app.database import get_db, save_additional_infos, get_additional_infos, save_color_settings, load_color_settings
from app.config import Config
from app.services.pdf_generator import create_pdf
from app.utils import parse_iso_datetime, normalize_newlines

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Helper functions
async def fetch_calendars(login_token: str):
    import httpx
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

async def fetch_appointment_details(login_token: str, appointment_id: str, start_date: str = None, end_date: str = None):
    """Holt die Details eines einzelnen Termins anhand seiner ID und berücksichtigt den Datumsbereich."""
    import httpx
    import pytz
    from datetime import datetime, timedelta
    
    # Die Termin-ID enthält die Kalender-ID und die Basis-ID, getrennt durch "_"
    # Format: "calendar_id_base_id" oder "calendar_id_base_id_counter"
    parts = appointment_id.split("_")
    
    if len(parts) < 2:
        logger.error(f"Ungültiges Format für Termin-ID: {appointment_id}")
        return None
    
    # Extrahiere die Kalender-ID (erster Teil)
    try:
        calendar_id = int(parts[0])
    except ValueError:
        logger.error(f"Kalender-ID ist keine gültige Zahl: {parts[0]}")
        return None
    
    # Extrahiere die Basis-ID (zweiter Teil)
    base_id = parts[1]
    
    # Wenn es einen Counter gibt (drittes Teil), ignorieren wir ihn hier
    
    # Wenn kein Datumsbereich angegeben ist, verwenden wir einen großzügigen Standardbereich
    if not start_date or not end_date:
        berlin_tz = pytz.timezone('Europe/Berlin')
        today = berlin_tz.localize(datetime.now())
        start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')  # 30 Tage in die Vergangenheit
        end_date = (today + timedelta(days=30)).strftime('%Y-%m-%d')    # 30 Tage in die Zukunft
    
    # Hole den Termin aus der API mit dem angegebenen Datumsbereich
    headers = {'Authorization': f'Login {login_token}'}
    query_params = {
        'from': start_date,
        'to': end_date
    }
    url = f'{Config.CHURCHTOOLS_BASE_URL}/api/calendars/{calendar_id}/appointments'
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=query_params)
            
            if response.status_code == 200:
                appointments = response.json().get('data', [])
                
                # Suche nach dem Termin mit der passenden Basis-ID
                matching_appointments = []
                for appointment in appointments:
                    if str(appointment['base']['id']) == base_id:
                        matching_appointments.append(appointment)
                
                if not matching_appointments:
                    logger.error(f"Termin mit Basis-ID {base_id} nicht gefunden in Kalender {calendar_id} für den Zeitraum {start_date} bis {end_date}")
                    return None
                
                # Wenn es mehrere passende Termine gibt, wähle den, der im ausgewählten Datumsbereich liegt
                if len(matching_appointments) > 1:
                    # Konvertiere start_date und end_date in datetime-Objekte
                    berlin_tz = pytz.timezone('Europe/Berlin')
                    start_dt = berlin_tz.localize(datetime.strptime(start_date, '%Y-%m-%d'))
                    end_dt = berlin_tz.localize(datetime.strptime(end_date, '%Y-%m-%d'))
                    
                    # Finde den Termin, der im ausgewählten Datumsbereich liegt
                    for appointment in matching_appointments:
                        appointment_start = parse_iso_datetime(appointment['calculated']['startDate'])
                        if start_dt <= appointment_start <= end_dt:
                            logger.info(f"Mehrere Termine mit Basis-ID {base_id} gefunden, wähle den im Datumsbereich {start_date} bis {end_date}")
                            return appointment
                
                # Wenn kein Termin im ausgewählten Datumsbereich liegt, nimm den ersten
                logger.warning(f"Kein Termin mit Basis-ID {base_id} im Datumsbereich {start_date} bis {end_date} gefunden, nehme den ersten passenden Termin")
                return matching_appointments[0]
                return None
            else:
                logger.error(f"Fehler beim Abrufen des Termins: {response.status_code}")
                return None
    except Exception as e:
        logger.error(f"Fehler beim Abrufen des Termins: {e}")
        return None

async def fetch_appointments(login_token: str, start_date: str, end_date: str, calendar_ids: List[int]):
    import httpx
    import pytz
    from datetime import datetime
    
    berlin_tz = pytz.timezone('Europe/Berlin')
    start_date_datetime = berlin_tz.localize(datetime.strptime(start_date, '%Y-%m-%d'))
    end_date_datetime = berlin_tz.localize(datetime.strptime(end_date, '%Y-%m-%d'))

    headers = {'Authorization': f'Login {login_token}'}
    query_params = {
        'from': (start_date_datetime.strftime('%Y-%m-%d')),
        'to': (end_date_datetime.strftime('%Y-%m-%d'))
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

def get_date_range_from_form(start_date: str = None, end_date: str = None):
    today = datetime.today()
    next_sunday = today + timedelta(days=(6 - today.weekday()) % 7)
    sunday_after_next = next_sunday + timedelta(weeks=1)
    
    if not start_date:
        start_date = next_sunday.strftime('%Y-%m-%d')
    if not end_date:
        end_date = sunday_after_next.strftime('%Y-%m-%d')
        
    return start_date, end_date

# This function was removed because it is not used

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
        {
            "request": request,
            "calendars": calendars,
            "selected_calendar_ids": selected_calendar_ids,
            "start_date": start_date,
            "end_date": end_date,
            "base_url": Config.CHURCHTOOLS_BASE,
            "color_settings": color_settings,
            "version": Config.VERSION
        }
    )

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
    
    # Default values for color settings
    color_settings = load_color_settings(db, "default")
    
    # Override with form data if available
    if background_color:
        color_settings['background_color'] = background_color
    if alpha is not None:
        color_settings['background_alpha'] = alpha
    if date_color:
        color_settings['date_color'] = date_color
    if description_color:
        color_settings['description_color'] = description_color
    
    if fetch_appointments_btn:
        # Fetch appointments
        appointments_data = await fetch_appointments(login_token, start_date, end_date, calendar_ids_int)
        appointments = [appointment_to_dict(app) for app in appointments_data]
        
        # Load additional information
        additional_infos = get_additional_infos(db, [appointment['id'] for appointment in appointments])
        for appointment in appointments:
            appointment['additional_info'] = additional_infos.get(appointment['id'], "")
        
        # Load color settings
        color_settings = load_color_settings(db, "default")
        
        response = templates.TemplateResponse(
            "appointments.html",
            {
                "request": request,
                "calendars": calendars,
                "selected_calendar_ids": calendar_ids,
                "appointments": appointments,
                "start_date": start_date,
                "end_date": end_date,
                "base_url": Config.CHURCHTOOLS_BASE,
                "color_settings": color_settings,
                "version": Config.VERSION
            }
        )
        response.set_cookie(key="fetchAppointments", value="true", max_age=1, path='/')
        return response
    
    elif generate_pdf_btn:
        if not appointment_id:
            # If no appointments were selected, return to appointment overview
            return templates.TemplateResponse(
                "appointments.html",
                {
                    "request": request,
                    "calendars": calendars,
                    "selected_calendar_ids": calendar_ids,
                    "start_date": start_date,
                    "end_date": end_date,
                    "base_url": Config.CHURCHTOOLS_BASE,
                    "color_settings": color_settings,
                    "error": "Please select at least one appointment.",
                    "version": Config.VERSION
                }
            )
            
        # Save additional information
        appointment_info_list = []
        form_data = await request.form()
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
                if content:  # Nur verarbeiten, wenn Inhalt vorhanden ist
                    background_image_stream = BytesIO(content)
            except Exception as e:
                print(f"Error reading background image: {e}")
        
        # Get the actual appointments from the API
        logger.info(f"Selected appointment IDs: {appointment_id}")
        logger.info(f"Retrieving appointments for period {start_date} to {end_date} and calendars {calendar_ids_int}")
        
        # Wir holen alle Termine für den angegebenen Zeitraum und die ausgewählten Kalender
        appointments_data = await fetch_appointments(login_token, start_date, end_date, calendar_ids_int)
        logger.info(f"Number of retrieved appointments: {len(appointments_data)}")
        
        # Konvertiere die Termine in das richtige Format
        appointments = [appointment_to_dict(app) for app in appointments_data]
        
        # Sammle die zusätzlichen Informationen aus dem Formular
        form_data = await request.form()
        
        # Füge die zusätzlichen Informationen zu den Terminen hinzu
        for appointment in appointments:
            app_id = appointment['id']
            additional_info = form_data.get(f'additional_info_{app_id}', "")
            appointment['additional_info'] = additional_info
        
        # Filtere die ausgewählten Termine
        selected_appointments = []
        for app_id in appointment_id:
            # Finde alle Termine mit der passenden ID
            matching_appointments = [app for app in appointments if str(app['id']) == str(app_id)]
            # Füge alle passenden Termine hinzu
            selected_appointments.extend(matching_appointments)
        
        logger.info(f"Number of selected appointments: {len(selected_appointments)}")
        
        # Wir haben bereits die ausgewählten Termine in selected_appointments
        
        # Sortiere die Termine nach dem Startdatum
        selected_appointments.sort(key=lambda x: parse_iso_datetime(x['startDate']))
        
        # Logging for selected appointments
        logger.info(f"Generating PDF for {len(selected_appointments)} appointments:")
        for idx, app in enumerate(selected_appointments, 1):
            logger.info(f"  {idx}. {app['description']} am {app['startDateView']} ({app['startTimeView']}-{app['endTimeView']})")
        
        # Create PDF
        filename = create_pdf(selected_appointments, color_settings['date_color'], color_settings['background_color'],
                            color_settings['description_color'], color_settings['background_alpha'],
                            background_image_stream)
        
        response = RedirectResponse(url=f"/download/{filename}", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key="pdfGenerated", value="true", max_age=1, path='/')
        return response
    
    elif generate_jpeg_btn:
        if not appointment_id:
            # If no appointments were selected, return to appointment overview
            return templates.TemplateResponse(
                "appointments.html",
                {
                    "request": request,
                    "calendars": calendars,
                    "selected_calendar_ids": calendar_ids,
                    "start_date": start_date,
                    "end_date": end_date,
                    "base_url": Config.CHURCHTOOLS_BASE,
                    "color_settings": color_settings,
                    "error": "Please select at least one appointment.",
                    "version": Config.VERSION
                }
            )
            
        # Similar to PDF, but with JPEG conversion
        appointment_info_list = []
        form_data = await request.form()
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
                if content:  # Nur verarbeiten, wenn Inhalt vorhanden ist
                    background_image_stream = BytesIO(content)
            except Exception as e:
                print(f"Error reading background image: {e}")
        
        # Wir holen alle Termine für den angegebenen Zeitraum und die ausgewählten Kalender
        appointments_data = await fetch_appointments(login_token, start_date, end_date, calendar_ids_int)
        logger.info(f"Number of retrieved appointments: {len(appointments_data)}")
        
        # Konvertiere die Termine in das richtige Format
        appointments = [appointment_to_dict(app) for app in appointments_data]
        
        # Füge die zusätzlichen Informationen zu den Terminen hinzu
        for appointment in appointments:
            app_id = appointment['id']
            additional_info = form_data.get(f'additional_info_{app_id}', "")
            appointment['additional_info'] = additional_info
        
        # Filtere die ausgewählten Termine
        selected_appointments = []
        for app_id in appointment_id:
            # Finde alle Termine mit der passenden ID
            matching_appointments = [app for app in appointments if str(app['id']) == str(app_id)]
            # Füge alle passenden Termine hinzu
            selected_appointments.extend(matching_appointments)
        
        logger.info(f"Number of selected appointments for JPEG: {len(selected_appointments)}")
        
        # Sortiere die Termine nach dem Startdatum
        selected_appointments.sort(key=lambda x: parse_iso_datetime(x['startDate']))
        
        # Logging for selected appointments
        logger.info(f"Generating JPEG for {len(selected_appointments)} appointments:")
        for idx, app in enumerate(selected_appointments, 1):
            logger.info(f"  {idx}. {app['description']} am {app['startDateView']} ({app['startTimeView']}-{app['endTimeView']})")
        
        # Create PDF
        filename = create_pdf(selected_appointments, color_settings['date_color'], color_settings['background_color'],
                            color_settings['description_color'], color_settings['background_alpha'],
                            background_image_stream)
        
        # Generate JPEG
        zip_filename = handle_jpeg_generation(filename)
        
        # Return as file
        response = FileResponse(
            os.path.join(Config.FILE_DIRECTORY, zip_filename),
            media_type="application/zip",
            filename=zip_filename
        )
        response.set_cookie(key="jpegGenerated", value="true", max_age=1, path='/')
        return response
    
    # Default case: Show form
    return templates.TemplateResponse(
        "appointments.html",
        {
            "request": request,
            "calendars": calendars,
            "selected_calendar_ids": calendar_ids,
            "start_date": start_date,
            "end_date": end_date,
            "base_url": Config.CHURCHTOOLS_BASE,
            "color_settings": color_settings,
            "version": Config.VERSION
        }
    )

@router.get("/download/{filename}")
async def download_file(filename: str):
    file_path = os.path.join(Config.FILE_DIRECTORY, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(file_path, filename=filename)