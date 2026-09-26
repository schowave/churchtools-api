import json
import threading
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient

from app.api.appointments import api_generate, appointments_page
from app.config import settings
from app.database import get_db
from app.main import app
from app.schemas import ColorSettings, GenerateRequest
from app.services.churchtools_client import AuthenticationError
from app.web import get_http_client


@pytest.fixture
def templates_mock():
    templates_mock = MagicMock(spec=Jinja2Templates)
    with patch("app.api.calendar_pages.templates", templates_mock):
        yield templates_mock


SAMPLE_APPOINTMENT_DATA = [
    {
        "base": {
            "id": "1_101_2023-01-15T10:00:00Z",
            "caption": "Event 1",
            "information": "Info 1",
            "address": {"meetingAt": "Location 1"},
        },
        "calculated": {
            "startDate": "2023-01-15T10:00:00Z",
            "endDate": "2023-01-15T12:00:00Z",
        },
    },
]


@pytest.mark.asyncio
@patch("app.api.appointments.load_background_image", return_value=(None, None))
@patch("app.api.appointments.load_logo", return_value=(None, None))
@patch("app.api.calendar_pages.fetch_calendars")
@patch("app.api.calendar_pages.get_date_range_from_form")
@patch("app.api.appointments.load_color_settings")
async def test_appointments_page_with_token(
    mock_load_color,
    mock_get_date,
    mock_fetch_cal,
    mock_load_logo,
    mock_load_bg,
    templates_mock,
    config_mock,
):
    # Mock request with login_token
    request_mock = MagicMock(spec=Request)
    request_mock.cookies.get.return_value = "test_token"

    # Mock database session
    db_mock = MagicMock()

    # Mock http client
    client_mock = AsyncMock()

    # Mock return values
    mock_get_date.return_value = ("2023-01-15", "2023-01-22")
    mock_fetch_cal.return_value = [{"id": 1, "name": "Calendar 1"}, {"id": 2, "name": "Calendar 2"}]
    mock_load_color.return_value = ColorSettings(name="default")

    # Call the function (page renders without appointments, AJAX loads them later)
    await appointments_page(request_mock, db_mock, client_mock, start_date=None, end_date=None, calendar_ids=None)

    # Check that fetch_calendars was called with the token and client
    mock_fetch_cal.assert_called_once_with("test_token", client_mock)

    # Check that templates.TemplateResponse was called with correct parameters
    templates_mock.TemplateResponse.assert_called_once()
    call_args = templates_mock.TemplateResponse.call_args[0]
    context = call_args[2]

    assert call_args[1] == "appointments.html"
    assert "calendars" in context
    assert "selected_calendar_ids" in context
    assert "start_date" in context
    assert "end_date" in context
    assert "base_url" in context
    assert "color_settings" in context
    assert context["calendars"] == mock_fetch_cal.return_value
    assert context["selected_calendar_ids"] == ["1", "2"]
    assert context["start_date"] == "2023-01-15"
    assert context["end_date"] == "2023-01-22"
    assert context["base_url"] == config_mock["CHURCHTOOLS_BASE"]
    assert context["color_settings"] == ColorSettings(name="default")


@pytest.mark.asyncio
@patch("app.api.calendar_pages.fetch_calendars")
async def test_appointments_page_without_token(mock_fetch):
    # Mock request without login_token
    request_mock = MagicMock(spec=Request)
    request_mock.cookies.get.return_value = None

    # Mock database session
    db_mock = MagicMock()

    # Mock http client
    client_mock = AsyncMock()

    # Call the function
    result = await appointments_page(request_mock, db_mock, client_mock)

    # Check that the result is a RedirectResponse
    assert isinstance(result, RedirectResponse)
    assert result.status_code == 303
    assert result.headers["location"] == "/"

    # Check that fetch_calendars was not called
    mock_fetch.assert_not_called()


@pytest.mark.asyncio
@patch("app.api.appointments.get_additional_infos", return_value={})
@patch("app.api.appointments.fetch_appointments")
async def test_api_appointments(
    mock_fetch_app,
    mock_get_info,
    templates_mock,
    config_mock,
):
    """GET /api/appointments should return JSON with appointments."""
    from app.api.appointments import api_appointments

    request = MagicMock(spec=Request)
    request.cookies.get.return_value = "test_token"
    db = MagicMock()
    client = AsyncMock()

    mock_fetch_app.return_value = SAMPLE_APPOINTMENT_DATA
    mock_get_info.return_value = {"1_101_2023-01-15T10:00:00Z": "Saved info"}

    response = await api_appointments(
        request=request,
        db=db,
        client=client,
        start_date="2023-01-15",
        end_date="2023-01-22",
        calendar_ids=["1", "2"],
    )

    assert response.status_code == 200
    mock_fetch_app.assert_called_once_with("test_token", "2023-01-15", "2023-01-22", [1, 2], client)
    assert json.loads(response.body)["appointments"][0]["additional_info"] == "Saved info"


APPOINTMENT_ID = "1_101_2023-01-15T10:00:00Z"


@pytest.mark.asyncio
@patch("app.api.appointments.claim_legacy_additional_infos", return_value={APPOINTMENT_ID: "Old text"})
@patch("app.api.appointments.get_additional_infos", return_value={})
@patch("app.api.appointments.fetch_appointments")
async def test_api_appointments_migrates_texts_saved_under_old_ids(
    mock_fetch_app, mock_get_info, mock_claim, config_mock
):
    """Custom texts saved before the id change are looked up under the old id and moved."""
    from app.api.appointments import api_appointments

    request = MagicMock(spec=Request)
    request.cookies.get.return_value = "test_token"
    mock_fetch_app.return_value = SAMPLE_APPOINTMENT_DATA

    response = await api_appointments(
        request=request,
        db=MagicMock(),
        client=AsyncMock(),
        start_date="2023-01-15",
        end_date="2023-01-22",
        calendar_ids=["1"],
    )

    mock_claim.assert_called_once_with(ANY, {APPOINTMENT_ID: "1_101"})
    assert json.loads(response.body)["appointments"][0]["additional_info"] == "Old text"


@pytest.mark.asyncio
@patch("app.api.appointments.load_background_image", return_value=(None, None))
@patch("app.api.appointments.load_logo", return_value=(None, None))
@patch("app.api.appointments.create_pdf")
@patch("app.api.appointments.save_color_settings")
@patch("app.api.appointments.save_additional_infos")
@patch("app.api.appointments.fetch_appointments")
async def test_api_generate_pdf(
    mock_fetch_app,
    mock_save_info,
    mock_save_color,
    mock_create_pdf,
    mock_load_logo,
    mock_load_bg,
    config_mock,
):
    """POST /api/generate with type=pdf should return StreamingResponse with PDF."""
    from fastapi.responses import StreamingResponse

    request = MagicMock(spec=Request)
    request.cookies.get.return_value = "test_token"
    db = MagicMock()
    client = AsyncMock()

    mock_fetch_app.return_value = SAMPLE_APPOINTMENT_DATA
    mock_create_pdf.return_value = b"%PDF-1.4 fake pdf content"

    body = GenerateRequest(
        type="pdf",
        start_date="2023-01-15",
        end_date="2023-01-22",
        calendar_ids=["1"],
        appointment_ids=["1_101_2023-01-15T10:00:00Z"],
        color_settings={
            "background_color": "#0000ff",
            "background_alpha": 100,
            "date_color": "#ff0000",
            "description_color": "#00ff00",
        },
        additional_infos={"1_101_2023-01-15T10:00:00Z": "Extra info"},
    )

    response = await api_generate(request=request, body=body, db=db, client=client)

    assert isinstance(response, StreamingResponse)
    assert response.media_type == "application/pdf"
    assert "_appointments.pdf" in response.headers["content-disposition"]

    # Verify PDF was created with correct color settings
    mock_create_pdf.assert_called_once()
    call_args = mock_create_pdf.call_args
    assert call_args[0][1] == "#ff0000"  # date_color
    assert call_args[0][2] == "#0000ff"  # background_color
    assert call_args[0][3] == "#00ff00"  # description_color
    assert call_args[0][4] == 100  # alpha

    # Verify additional infos were saved
    mock_save_info.assert_called_once()
    save_args = mock_save_info.call_args[0]
    assert save_args[1] == [("1_101_2023-01-15T10:00:00Z", "Extra info")]

    # Verify color settings were saved with name="default"
    mock_save_color.assert_called_once()
    saved_cs = mock_save_color.call_args[0][1]
    assert saved_cs.name == "default"


@pytest.mark.asyncio
@patch("app.api.appointments.load_background_image", return_value=(None, None))
@patch("app.api.appointments.load_logo", return_value=(None, None))
@patch("app.api.appointments.handle_jpeg_generation")
@patch("app.api.appointments.create_pdf")
@patch("app.api.appointments.save_color_settings")
@patch("app.api.appointments.save_additional_infos")
@patch("app.api.appointments.fetch_appointments")
async def test_api_generate_jpeg(
    mock_fetch_app,
    mock_save_info,
    mock_save_color,
    mock_create_pdf,
    mock_jpeg,
    mock_load_logo,
    mock_load_bg,
    config_mock,
):
    """POST /api/generate with type=jpeg should return StreamingResponse with ZIP."""
    from fastapi.responses import StreamingResponse

    request = MagicMock(spec=Request)
    request.cookies.get.return_value = "test_token"
    db = MagicMock()
    client = AsyncMock()

    pdf_bytes = b"%PDF-1.4 fake pdf content"
    zip_bytes = b"PK fake zip content"

    mock_fetch_app.return_value = SAMPLE_APPOINTMENT_DATA
    mock_create_pdf.return_value = pdf_bytes
    mock_jpeg.return_value = zip_bytes

    body = GenerateRequest(
        type="jpeg",
        start_date="2023-01-15",
        end_date="2023-01-22",
        calendar_ids=["1"],
        appointment_ids=["1_101_2023-01-15T10:00:00Z"],
        color_settings={
            "background_color": "#ffffff",
            "background_alpha": 128,
            "date_color": "#c1540c",
            "description_color": "#4e4e4e",
        },
        additional_infos={},
    )

    response = await api_generate(request=request, body=body, db=db, client=client)

    assert isinstance(response, StreamingResponse)
    assert response.media_type == "application/zip"
    assert "_appointments.zip" in response.headers["content-disposition"]
    mock_jpeg.assert_called_once_with(pdf_bytes)


@pytest.mark.asyncio
async def test_api_generate_no_auth():
    """POST /api/generate without token should return 401."""
    request = MagicMock(spec=Request)
    request.cookies.get.return_value = None
    db = MagicMock()
    client = AsyncMock()

    body = GenerateRequest(
        type="pdf",
        start_date="2023-01-15",
        end_date="2023-01-22",
        calendar_ids=["1"],
        appointment_ids=["1_101_2023-01-15T10:00:00Z"],
        color_settings={
            "background_color": "#ffffff",
            "background_alpha": 128,
            "date_color": "#c1540c",
            "description_color": "#4e4e4e",
        },
        additional_infos={},
    )

    response = await api_generate(request=request, body=body, db=db, client=client)
    assert response.status_code == 401


@pytest.mark.asyncio
@patch("app.api.appointments.load_background_image", return_value=(None, None))
@patch("app.api.appointments.load_logo", return_value=(None, None))
@patch("app.api.appointments.fetch_appointments")
async def test_api_generate_auth_error_mid_session(
    mock_fetch_app,
    mock_load_logo,
    mock_load_bg,
    config_mock,
):
    """If fetch_appointments raises AuthenticationError, should return 401."""
    request = MagicMock(spec=Request)
    request.cookies.get.return_value = "expired_token"
    db = MagicMock()
    client = AsyncMock()

    mock_fetch_app.side_effect = AuthenticationError()

    body = GenerateRequest(
        type="pdf",
        start_date="2023-01-15",
        end_date="2023-01-22",
        calendar_ids=["1"],
        appointment_ids=["1_101_2023-01-15T10:00:00Z"],
        color_settings={
            "background_color": "#ffffff",
            "background_alpha": 128,
            "date_color": "#c1540c",
            "description_color": "#4e4e4e",
        },
        additional_infos={},
    )

    response = await api_generate(request=request, body=body, db=db, client=client)
    assert response.status_code == 401


@pytest.fixture
def client():
    app.dependency_overrides[get_http_client] = lambda: AsyncMock()
    app.dependency_overrides[get_db] = lambda: None
    yield TestClient(app, cookies={settings.cookie_session: "token", "csrf_token": "t"})
    app.dependency_overrides.clear()


GENERATE_BODY = {
    "type": "jpeg",
    "start_date": "2026-09-27",
    "end_date": "2026-10-04",
    "calendar_ids": ["1"],
    "appointment_ids": ["1_1"],
    "color_settings": {"name": "default"},
}


def test_pdf_and_jpeg_generation_run_off_the_event_loop(client):
    threads = {}

    async def fake_fetch(*args, **kwargs):
        threads["loop"] = threading.get_ident()
        return []

    def fake_create_pdf(*args, **kwargs):
        threads["pdf"] = threading.get_ident()
        return b"%PDF"

    def fake_jpeg(pdf_bytes):
        threads["jpeg"] = threading.get_ident()
        return b"PK"

    with (
        patch("app.api.appointments.fetch_appointments", fake_fetch),
        patch("app.api.appointments.create_pdf", fake_create_pdf),
        patch("app.api.appointments.handle_jpeg_generation", fake_jpeg),
        patch("app.api.appointments.save_additional_infos"),
        patch("app.api.appointments.save_color_settings"),
        patch("app.api.appointments.load_logo", return_value=(None, None)),
        patch("app.api.appointments.load_background_image", return_value=(None, None)),
    ):
        response = client.post("/api/generate", json=GENERATE_BODY, headers={"X-CSRF-Token": "t"})

    assert response.status_code == 200
    assert threads["pdf"] != threads["loop"]
    assert threads["jpeg"] != threads["loop"]


def test_generate_ignores_client_supplied_profile(client):
    with (
        patch("app.api.appointments.fetch_appointments", AsyncMock(return_value=[])),
        patch("app.api.appointments.create_pdf", return_value=b"%PDF"),
        patch("app.api.appointments.save_additional_infos"),
        patch("app.api.appointments.save_color_settings"),
        patch("app.api.appointments.load_logo", return_value=(None, None)) as load_logo,
        patch("app.api.appointments.load_background_image", return_value=(None, None)) as load_bg,
    ):
        body = {**GENERATE_BODY, "type": "pdf", "profile": "someone-else"}
        response = client.post("/api/generate", json=body, headers={"X-CSRF-Token": "t"})

    assert response.status_code == 200
    assert load_logo.call_args[0][1] == "default"
    assert load_bg.call_args[0][1] == "default"
