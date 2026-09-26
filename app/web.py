import httpx2
from fastapi import HTTPException, Request
from fastapi.templating import Jinja2Templates

from app.config import APP_DIR
from app.dates import validate_date_range
from app.schemas import MAX_CALENDARS

templates = Jinja2Templates(directory=APP_DIR / "templates")


def initials(name: str | None) -> str:
    """Initials for the navigation: first letters of the first and last word ("Erika Muster" -> "EM")."""
    words = (name or "").split()
    if not words:
        return ""
    letters = words[0][0] + (words[-1][0] if len(words) > 1 else "")
    return letters.upper()


templates.env.filters["initials"] = initials


def get_http_client(request: Request) -> httpx2.AsyncClient:
    return request.app.state.http_client


def check_range_query(start_date: str, end_date: str, calendar_ids: list[str]) -> None:
    """Reject date ranges and calendar selections too large to forward to ChurchTools (HTTP 422)."""
    try:
        validate_date_range(start_date, end_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    if len(calendar_ids) > MAX_CALENDARS:
        raise HTTPException(status_code=422, detail=f"Höchstens {MAX_CALENDARS} Kalender auswählbar")
