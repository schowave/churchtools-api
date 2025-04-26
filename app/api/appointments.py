from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, File, UploadFile, Cookie
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import zipfile
from io import BytesIO
from pdf2image import convert_from_path
from datetime import datetime, timedelta

from app.database import get_db, save_additional_infos, get_additional_infos, save_color_settings, load_color_settings
from app.config import Config
from app.services.pdf_generator import create_pdf
from app.utils import parse_iso_datetime, normalize_newlines

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Hilfsfunktionen
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

def handle_pdf_generation(appointment_ids, color_settings, background_image_stream=None):
    selected_appointments = [app for app in appointments if str(app['id']) in appointment_ids]
    additional_infos = get_additional_infos(db, [appointment['id'] for appointment in selected_appointments])
    for appointment in selected_appointments:
        appointment['additional_info'] = additional_infos.get(appointment['id'], "")
    filename = create_pdf(selected_appointments, color_settings['date_color'], color_settings['background_color'],
                        color_settings['description_color'], color_settings['background_alpha'],
                        background_image_stream)
    return filename

def handle_jpeg_generation(pdf_filename):
    full_pdf_path = os.path.join(Config.FILE_DIRECTORY, pdf_filename)
    images = convert_from_path(full_pdf_path)
    jpeg_files = []

    for i, image in enumerate(images):
        jpeg_stream = BytesIO()
        image.save(jpeg_stream, 'JPEG')
        jpeg_stream.seek(0)
        jpeg_files.append((f'page_{i + 1}.jpg', jpeg_stream))

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED) as zip_file:
        for file_name, file_bytes in jpeg_files:
            zip_file.writestr(file_name, file_bytes.read())
    zip_buffer.seek(0)
    return zip_buffer

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
    
    # Vorauswahl aller Kalender
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
            "color_settings": color_settings
        }
    )

@router.post("/appointments")
async def process_appointments(
    request: Request,
    db: Session = Depends(get_db),
    fetch_appointments_btn: Optional[str] = Form(None, alias="fetch_appointments"),
    generate_pdf_btn: Optional[str] = Form(None, alias="generate_pdf"),
    generate_jpeg_btn: Optional[str] = Form(None, alias="generate_jpeg"),
    start_date: str = Form(...),
    end_date: str = Form(...),
    calendar_ids: List[str] = Form(...),
    appointment_id: Optional[List[str]] = Form(None),
    background_image: Optional[UploadFile] = File(None),
    date_color: Optional[str] = Form("#c1540c"),
    description_color: Optional[str] = Form("#4e4e4e"),
    background_color: Optional[str] = Form("#ffffff"),
    alpha: Optional[int] = Form(128)
):
    login_token = request.cookies.get("login_token")
    if not login_token:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    
    calendars = await fetch_calendars(login_token)
    
    # Konvertiere calendar_ids zu Integers
    calendar_ids_int = [int(id) for id in calendar_ids if id.isdigit()]
    
    color_settings = {
        'name': 'default',
        'background_color': background_color,
        'background_alpha': alpha,
        'date_color': date_color,
        'description_color': description_color
    }
    
    if fetch_appointments_btn:
        # Termine abholen
        appointments_data = await fetch_appointments(login_token, start_date, end_date, calendar_ids_int)
        appointments = [appointment_to_dict(app) for app in appointments_data]
        
        # Zusätzliche Informationen laden
        additional_infos = get_additional_infos(db, [appointment['id'] for appointment in appointments])
        for appointment in appointments:
            appointment['additional_info'] = additional_infos.get(appointment['id'], "")
        
        # Farbeinstellungen laden
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
                "color_settings": color_settings
            }
        )
        response.set_cookie(key="fetchAppointments", value="true", max_age=1, path='/')
        return response
    
    elif generate_pdf_btn and appointment_id:
        # Zusätzliche Informationen speichern
        appointment_info_list = []
        for app_id in appointment_id:
            additional_info = request.form.get(f'additional_info_{app_id}')
            normalized_info = normalize_newlines(additional_info)
            appointment_info_list.append((app_id, normalized_info))
        
        save_additional_infos(db, appointment_info_list)
        save_color_settings(db, color_settings)
        
        # Hintergrundbild verarbeiten
        background_image_stream = None
        if background_image:
            background_image_stream = BytesIO(await background_image.read())
        
        # PDF generieren
        appointments_data = await fetch_appointments(login_token, start_date, end_date, calendar_ids_int)
        appointments = [appointment_to_dict(app) for app in appointments_data]
        
        # Zusätzliche Informationen laden
        additional_infos = get_additional_infos(db, [appointment['id'] for appointment in appointments])
        for appointment in appointments:
            appointment['additional_info'] = additional_infos.get(appointment['id'], "")
        
        # Nur ausgewählte Termine verwenden
        selected_appointments = [app for app in appointments if app['id'] in appointment_id]
        
        # PDF erstellen
        filename = create_pdf(selected_appointments, color_settings['date_color'], color_settings['background_color'],
                            color_settings['description_color'], color_settings['background_alpha'],
                            background_image_stream)
        
        response = RedirectResponse(url=f"/download/{filename}", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key="pdfGenerated", value="true", max_age=1, path='/')
        return response
    
    elif generate_jpeg_btn and appointment_id:
        # Ähnlich wie bei PDF, aber mit JPEG-Konvertierung
        appointment_info_list = []
        for app_id in appointment_id:
            additional_info = request.form.get(f'additional_info_{app_id}')
            normalized_info = normalize_newlines(additional_info)
            appointment_info_list.append((app_id, normalized_info))
        
        save_additional_infos(db, appointment_info_list)
        save_color_settings(db, color_settings)
        
        # Hintergrundbild verarbeiten
        background_image_stream = None
        if background_image:
            background_image_stream = BytesIO(await background_image.read())
        
        # PDF generieren und dann in JPEG konvertieren
        appointments_data = await fetch_appointments(login_token, start_date, end_date, calendar_ids_int)
        appointments = [appointment_to_dict(app) for app in appointments_data]
        
        # Zusätzliche Informationen laden
        additional_infos = get_additional_infos(db, [appointment['id'] for appointment in appointments])
        for appointment in appointments:
            appointment['additional_info'] = additional_infos.get(appointment['id'], "")
        
        # Nur ausgewählte Termine verwenden
        selected_appointments = [app for app in appointments if app['id'] in appointment_id]
        
        # PDF erstellen
        filename = create_pdf(selected_appointments, color_settings['date_color'], color_settings['background_color'],
                            color_settings['description_color'], color_settings['background_alpha'],
                            background_image_stream)
        
        # JPEG generieren
        zip_buffer = handle_jpeg_generation(filename)
        
        # Als Datei zurückgeben
        response = FileResponse(
            zip_buffer,
            media_type="application/zip",
            filename="images.zip"
        )
        response.set_cookie(key="jpegGenerated", value="true", max_age=1, path='/')
        return response
    
    # Standardfall: Formular anzeigen
    return templates.TemplateResponse(
        "appointments.html",
        {
            "request": request,
            "calendars": calendars,
            "selected_calendar_ids": calendar_ids,
            "start_date": start_date,
            "end_date": end_date,
            "base_url": Config.CHURCHTOOLS_BASE,
            "color_settings": color_settings
        }
    )

@router.get("/download/{filename}")
async def download_file(filename: str):
    file_path = os.path.join(Config.FILE_DIRECTORY, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(file_path, filename=filename)