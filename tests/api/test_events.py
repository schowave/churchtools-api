from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.events import api_agenda_pdf, api_event_agenda, api_event_services_pdf, api_events
from app.schemas import AgendaItem, EventService, EventSummary


@pytest.mark.asyncio
@patch("app.api.events.fetch_events")
async def test_api_events_success(mock_fetch, config_mock):
    from fastapi import Request

    request = MagicMock(spec=Request)
    request.cookies.get.return_value = "token"
    client = AsyncMock()

    mock_fetch.return_value = [
        EventSummary(
            id=1,
            name="Gottesdienst",
            start_date="2026-03-22T09:00:00Z",
            end_date="2026-03-22T11:00:00Z",
            calendar_name="GD",
            services=[EventService(service_id=1, name="Predigt", person_name="Max", is_accepted=True)],
        )
    ]

    response = await api_events(
        request=request,
        client=client,
        start_date="2026-03-22",
        end_date="2026-03-29",
        calendar_ids=["5"],
    )

    assert response.status_code == 200
    mock_fetch.assert_called_once_with("token", "2026-03-22", "2026-03-29", ["5"], client)


@pytest.mark.asyncio
async def test_api_events_no_auth(config_mock):
    from fastapi import Request

    request = MagicMock(spec=Request)
    request.cookies.get.return_value = None
    client = AsyncMock()

    response = await api_events(
        request=request,
        client=client,
        start_date="2026-03-22",
        end_date="2026-03-29",
        calendar_ids=["5"],
    )

    assert response.status_code == 401


@pytest.mark.asyncio
@patch("app.api.events.fetch_agenda")
async def test_api_event_agenda_success(mock_fetch, config_mock):
    from fastapi import Request

    request = MagicMock(spec=Request)
    request.cookies.get.return_value = "token"
    client = AsyncMock()

    mock_fetch.return_value = [
        AgendaItem(
            position=1,
            type="default",
            title="Begruessung",
            start="2026-03-22T09:00:00Z",
            duration_seconds=300,
            responsible_names=["Max"],
            is_before_event=False,
        ),
    ]

    response = await api_event_agenda(request=request, event_id=1, client=client)

    assert response.status_code == 200
    mock_fetch.assert_called_once_with("token", 1, client)


@pytest.mark.asyncio
@patch("app.api.events.fetch_agenda")
async def test_api_event_agenda_empty(mock_fetch, config_mock):
    from fastapi import Request

    request = MagicMock(spec=Request)
    request.cookies.get.return_value = "token"
    client = AsyncMock()
    mock_fetch.return_value = []

    response = await api_event_agenda(request=request, event_id=999, client=client)

    assert response.status_code == 200


@pytest.mark.asyncio
@patch("app.api.events.create_agenda_pdf")
@patch("app.api.events.fetch_agenda")
@patch("app.api.events.fetch_event")
async def test_api_agenda_pdf(mock_fetch_event, mock_fetch_agenda, mock_create_pdf, config_mock):
    from fastapi import Request
    from fastapi.responses import StreamingResponse

    request = MagicMock(spec=Request)
    request.cookies.get.return_value = "token"
    client = AsyncMock()

    mock_fetch_agenda.return_value = [
        AgendaItem(
            position=1,
            type="default",
            title="Begruessung",
            start="2026-03-22T09:00:00Z",
            duration_seconds=300,
            responsible_names=["Max"],
            is_before_event=False,
        ),
    ]
    mock_create_pdf.return_value = b"%PDF-1.4 fake"

    mock_fetch_event.return_value = EventSummary(
        id=1, name="Gottesdienst", start_date="2026-03-22T09:00:00Z", end_date="2026-03-22T10:00:00Z"
    )

    response = await api_agenda_pdf(request=request, event_id=1, client=client)

    assert isinstance(response, StreamingResponse)
    assert response.media_type == "application/pdf"
    # Title and start come from ChurchTools, not from client-supplied query parameters
    mock_fetch_event.assert_called_once_with("token", 1, client)
    assert mock_create_pdf.call_args[0][:2] == ("Gottesdienst", "2026-03-22T09:00:00Z")


@pytest.mark.asyncio
@patch("app.api.events.create_services_pdf")
@patch("app.api.events.fetch_events")
async def test_api_event_services_pdf(mock_fetch_events, mock_create_pdf, config_mock):
    from fastapi import Request
    from fastapi.responses import StreamingResponse

    request = MagicMock(spec=Request)
    request.cookies.get.return_value = "token"
    client = AsyncMock()

    mock_fetch_events.return_value = [
        EventSummary(
            id=1,
            name="GD",
            start_date="2026-03-22T09:00:00Z",
            end_date="2026-03-22T11:00:00Z",
            calendar_name="GD",
            services=[],
        ),
    ]
    mock_create_pdf.return_value = b"%PDF-1.4 fake"

    response = await api_event_services_pdf(
        request=request,
        event_id=1,
        client=client,
        start_date="2026-03-22",
        end_date="2026-03-29",
        calendar_ids=["5"],
    )

    assert isinstance(response, StreamingResponse)
    assert response.media_type == "application/pdf"
    assert mock_create_pdf.call_args[0][0] == "GD"
