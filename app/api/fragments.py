import structlog
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.crud import get_additional_infos
from app.database import get_db
from app.dependencies import get_http_client
from app.services.churchtools_client import AuthenticationError, fetch_appointments, parse_appointment
from app.shared import templates

logger = structlog.get_logger()
router = APIRouter(prefix="/fragments")


@router.get("/appointments")
async def fragment_appointments(
    request: Request,
    db: Session = Depends(get_db),
    start_date: str = Query(...),
    end_date: str = Query(...),
    calendar_ids: list[str] = Query(default=[]),
    client=Depends(get_http_client),
):
    login_token = request.cookies.get(settings.cookie_login_token)
    if not login_token:
        return HTMLResponse("<p>Nicht angemeldet</p>", status_code=401)

    calendar_ids_int = [int(cid) for cid in calendar_ids if cid.isdigit()]
    if not calendar_ids_int:
        return HTMLResponse("<p>Keine Kalender ausgewählt</p>")

    try:
        raw_appointments = await fetch_appointments(login_token, start_date, end_date, calendar_ids_int, client)
    except AuthenticationError:
        return HTMLResponse("<p>Sitzung abgelaufen</p>", status_code=401)

    appointments = [parse_appointment(raw) for raw in raw_appointments]
    additional_infos = get_additional_infos(db, [app.id for app in appointments])
    for appointment in appointments:
        appointment.additional_info = additional_infos.get(appointment.id, "")

    return templates.TemplateResponse(
        "fragments/appointments.html",
        {"request": request, "appointments": appointments},
    )
