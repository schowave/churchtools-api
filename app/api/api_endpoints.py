"""
API-Endpunkte für die ChurchTools-Integration.
Dieser Modul enthält reine API-Endpunkte, die JSON zurückgeben,
im Gegensatz zu den UI-Endpunkten, die HTML-Templates rendern.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, Body
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

from app.database import get_db, save_additional_infos, get_additional_infos, save_color_settings, load_color_settings
from app.config import Config
from app.utils.logging_config import APIError, log_exception
from app.api.appointments import fetch_calendars, fetch_appointments, appointment_to_dict, get_date_range_from_form

# Logger konfigurieren
logger = logging.getLogger("app.api.api_endpoints")

# Router erstellen
router = APIRouter(prefix="/api/v1", tags=["api"])

@router.get("/calendars")
async def get_calendars(request: Request):
    """
    Gibt alle verfügbaren Kalender zurück.
    
    Returns:
        Liste der verfügbaren Kalender
    """
    try:
        login_token = request.cookies.get("login_token")
        if not login_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Nicht authentifiziert"
            )
        
        calendars = await fetch_calendars(login_token)
        return {"calendars": calendars}
    except Exception as e:
        log_exception(logger, e, {"context": "Kalenderabruf"})
        raise APIError(
            message="Fehler beim Abrufen der Kalender",
            status_code=500,
            details={"error": str(e)}
        )

@router.get("/appointments")
async def get_appointments(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    calendar_ids: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Gibt Termine für den angegebenen Zeitraum und die angegebenen Kalender zurück.
    
    Args:
        start_date: Startdatum im Format YYYY-MM-DD
        end_date: Enddatum im Format YYYY-MM-DD
        calendar_ids: Kommagetrennte Liste von Kalender-IDs
        
    Returns:
        Liste der Termine
    """
    try:
        login_token = request.cookies.get("login_token")
        if not login_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Nicht authentifiziert"
            )
        
        # Standardwerte für Datumsbereich
        if not start_date or not end_date:
            start_date_default, end_date_default = get_date_range_from_form()
            start_date = start_date or start_date_default
            end_date = end_date or end_date_default
        
        # Kalender-IDs verarbeiten
        calendar_ids_int = []
        if calendar_ids:
            calendar_ids_int = [int(id) for id in calendar_ids.split(",") if id.isdigit()]
        
        # Wenn keine Kalender angegeben sind, alle verfügbaren Kalender verwenden
        if not calendar_ids_int:
            calendars = await fetch_calendars(login_token)
            calendar_ids_int = [calendar['id'] for calendar in calendars]
        
        # Termine abrufen
        appointments_data = await fetch_appointments(login_token, start_date, end_date, calendar_ids_int)
        appointments = [appointment_to_dict(app) for app in appointments_data]
        
        # Zusätzliche Informationen laden
        additional_infos = get_additional_infos(db, [appointment['id'] for appointment in appointments])
        for appointment in appointments:
            appointment['additional_info'] = additional_infos.get(appointment['id'], "")
        
        return {
            "appointments": appointments,
            "start_date": start_date,
            "end_date": end_date,
            "calendar_ids": calendar_ids_int
        }
    except Exception as e:
        log_exception(logger, e, {"context": "Terminabruf"})
        raise APIError(
            message="Fehler beim Abrufen der Termine",
            status_code=500,
            details={"error": str(e)}
        )

@router.post("/appointments/{appointment_id}/additional_info")
async def update_additional_info(
    appointment_id: str,
    additional_info: str = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    """
    Aktualisiert die zusätzlichen Informationen für einen Termin.
    
    Args:
        appointment_id: ID des Termins
        additional_info: Zusätzliche Informationen
        
    Returns:
        Erfolgsmeldung
    """
    try:
        save_additional_infos(db, [(appointment_id, additional_info)])
        return {"message": "Zusätzliche Informationen erfolgreich gespeichert"}
    except Exception as e:
        log_exception(logger, e, {"context": "Speichern zusätzlicher Informationen"})
        raise APIError(
            message="Fehler beim Speichern der zusätzlichen Informationen",
            status_code=500,
            details={"error": str(e)}
        )

@router.get("/color_settings")
async def get_color_settings(
    setting_name: str = "default",
    db: Session = Depends(get_db)
):
    """
    Gibt die Farbeinstellungen zurück.
    
    Args:
        setting_name: Name der Farbeinstellung
        
    Returns:
        Farbeinstellungen
    """
    try:
        color_settings = load_color_settings(db, setting_name)
        return color_settings
    except Exception as e:
        log_exception(logger, e, {"context": "Laden der Farbeinstellungen"})
        raise APIError(
            message="Fehler beim Laden der Farbeinstellungen",
            status_code=500,
            details={"error": str(e)}
        )

@router.post("/color_settings")
async def update_color_settings(
    settings: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """
    Aktualisiert die Farbeinstellungen.
    
    Args:
        settings: Farbeinstellungen
        
    Returns:
        Erfolgsmeldung
    """
    try:
        save_color_settings(db, settings)
        return {"message": "Farbeinstellungen erfolgreich gespeichert"}
    except Exception as e:
        log_exception(logger, e, {"context": "Speichern der Farbeinstellungen"})
        raise APIError(
            message="Fehler beim Speichern der Farbeinstellungen",
            status_code=500,
            details={"error": str(e)}
        )