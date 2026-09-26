from collections.abc import Callable

import httpx2
from fastapi import Request
from fastapi.responses import Response

from app.config import settings
from app.services.auth import get_valid_login_token, redirect_to_login
from app.services.churchtools_client import AuthenticationError, fetch_calendars
from app.shared import templates
from app.utils import get_date_range_from_form


async def render_calendar_page(
    request: Request,
    client: httpx2.AsyncClient,
    template_name: str,
    start_date: str | None,
    end_date: str | None,
    calendar_ids: list[str] | None,
    extra_context: Callable[[], dict] | None = None,
) -> Response:
    """Render a page with date range and calendar selection (Termin-Folien, Agenda, Dienstplan).

    Redirects to the login page if the token is missing or rejected. `extra_context` is
    only evaluated for authenticated requests.
    """
    login_token = await get_valid_login_token(request, client)
    if not login_token:
        return redirect_to_login(request)

    try:
        calendars = await fetch_calendars(login_token, client)
    except AuthenticationError:
        return redirect_to_login(request)

    default_start, default_end = get_date_range_from_form()
    context = {
        "calendars": calendars,
        # Preselect all calendars unless the query names some
        "selected_calendar_ids": calendar_ids or [str(calendar["id"]) for calendar in calendars],
        "start_date": start_date or default_start,
        "end_date": end_date or default_end,
        "base_url": settings.churchtools_base,
        "version": settings.version,
    }
    if extra_context:
        context.update(extra_context())
    return templates.TemplateResponse(request, template_name, context)
