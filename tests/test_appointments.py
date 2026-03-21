from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.api.appointments import api_generate, appointments_page
from app.config import settings
from app.schemas import AppointmentData, ColorSettings, GenerateRequest
from app.services.churchtools_client import AuthenticationError, fetch_appointments, fetch_calendars, parse_appointment
from app.services.jpeg_generator import handle_jpeg_generation


@pytest.fixture
def templates_mock():
    templates_mock = MagicMock(spec=Jinja2Templates)
    with patch("app.api.appointments.templates", templates_mock):
        yield templates_mock


@pytest.fixture
def config_mock():
    values = {
        "CHURCHTOOLS_BASE": "test.church.tools",
        "CHURCHTOOLS_BASE_URL": "https://test.church.tools",
    }
    with (
        patch.object(settings, "churchtools_base", values["CHURCHTOOLS_BASE"]),
        patch.object(settings, "churchtools_base_url", values["CHURCHTOOLS_BASE_URL"]),
        patch.object(settings, "version", "0.0.0-test"),
    ):
        yield values


@pytest.mark.asyncio
async def test_fetch_calendars_success(config_mock):
    # Mock httpx client
    client = AsyncMock()

    # Mock successful response
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "data": [
            {"id": 1, "name": "Calendar 1", "isPublic": True},
            {"id": 2, "name": "Calendar 2", "isPublic": False},
            {"id": 3, "name": "Calendar 3", "isPublic": True},
        ]
    }
    client.get.return_value = response

    # Call the function
    result = await fetch_calendars("test_token", client)

    # Check that client.get was called with correct parameters
    client.get.assert_called_once_with(
        f"{config_mock['CHURCHTOOLS_BASE_URL']}/api/calendars", headers={"Authorization": "Login test_token"}
    )

    # Check that only public calendars were returned
    assert len(result) == 2
    assert result[0]["id"] == 1
    assert result[1]["id"] == 3


@pytest.mark.asyncio
async def test_fetch_calendars_auth_error():
    # Mock httpx client
    client = AsyncMock()

    # Mock 401 response
    response = MagicMock()
    response.status_code = 401
    client.get.return_value = response

    # Call the function and check that it raises AuthenticationError
    with pytest.raises(AuthenticationError):
        await fetch_calendars("invalid_token", client)


@pytest.mark.asyncio
async def test_fetch_appointments(config_mock):
    # Mock httpx client
    client = AsyncMock()

    # Mock successful responses for two calendars
    response1 = MagicMock()
    response1.status_code = 200
    response1.json.return_value = {
        "data": [
            {
                "base": {
                    "id": "101",
                    "caption": "Event 1",
                    "information": "Info 1",
                    "address": {"meetingAt": "Location 1"},
                },
                "calculated": {"startDate": "2023-01-15T10:00:00Z", "endDate": "2023-01-15T12:00:00Z"},
            }
        ]
    }

    response2 = MagicMock()
    response2.status_code = 200
    response2.json.return_value = {
        "data": [
            {
                "base": {
                    "id": "102",
                    "caption": "Event 2",
                    "information": "Info 2",
                    "address": {"meetingAt": "Location 2"},
                },
                "calculated": {"startDate": "2023-01-16T14:00:00Z", "endDate": "2023-01-16T16:00:00Z"},
            }
        ]
    }

    # Set up client to return different responses for different calendar IDs
    client.get.side_effect = [response1, response2]

    # Call the function
    result = await fetch_appointments("test_token", "2023-01-15", "2023-01-16", [1, 2], client)

    # Check that client.get was called twice with correct parameters
    assert client.get.call_count == 2
    client.get.assert_any_call(
        f"{config_mock['CHURCHTOOLS_BASE_URL']}/api/calendars/1/appointments",
        headers={"Authorization": "Login test_token"},
        params={"from": "2023-01-15", "to": "2023-01-16"},
    )
    client.get.assert_any_call(
        f"{config_mock['CHURCHTOOLS_BASE_URL']}/api/calendars/2/appointments",
        headers={"Authorization": "Login test_token"},
        params={"from": "2023-01-15", "to": "2023-01-16"},
    )

    # Check that appointments were returned and IDs were modified
    assert len(result) == 2
    assert result[0]["base"]["id"] == "1_101"
    assert result[1]["base"]["id"] == "2_102"


def test_parse_appointment():
    # Test with deprecated fields (caption/information) - fallback path
    raw = {
        "base": {
            "id": "1_101",
            "caption": "Test Event",
            "information": "Test Info",
            "address": {"meetingAt": "Test Location"},
        },
        "calculated": {"startDate": "2023-01-15T10:00:00Z", "endDate": "2023-01-15T12:00:00Z"},
    }

    result = parse_appointment(raw)

    assert isinstance(result, AppointmentData)
    assert result.id == "1_101"
    assert result.title == "Test Event"
    assert result.start_date == "2023-01-15T10:00:00Z"
    assert result.end_date == "2023-01-15T12:00:00Z"
    assert result.information == "Test Info"
    assert result.meeting_at == "Test Location"
    assert result.start_date_view == "15.01.2023"
    assert result.start_time_view == "11:00"  # UTC+1 for Berlin
    assert result.end_time_view == "13:00"  # UTC+1 for Berlin
    assert result.additional_info == ""


def test_parse_appointment_with_new_fields():
    # Test with new API fields (title/description) - preferred path
    raw = {
        "base": {
            "id": "1_101",
            "title": "New Title",
            "caption": "Old Caption",
            "description": "New Description",
            "information": "Old Info",
            "address": {"name": "Church Hall"},
        },
        "calculated": {"startDate": "2023-01-15T10:00:00Z", "endDate": "2023-01-15T12:00:00Z"},
    }

    result = parse_appointment(raw)

    # Should prefer new fields over deprecated ones
    assert result.title == "New Title"
    assert result.information == "New Description"
    assert result.meeting_at == "Church Hall"


def test_parse_appointment_missing_address():
    raw = {
        "base": {"id": "1_102", "caption": "Test Event 2", "information": "Test Info 2", "address": None},
        "calculated": {"startDate": "2023-01-16T14:00:00Z", "endDate": "2023-01-16T16:00:00Z"},
    }

    result = parse_appointment(raw)

    assert result.meeting_at == ""


def test_parse_appointment_nested_format():
    # Test the OpenAPI spec format: data[].appointment.base
    raw = {
        "appointment": {
            "base": {
                "id": "1_103",
                "title": "Nested Event",
                "address": {},
            },
            "calculated": {"startDate": "2023-01-17T09:00:00Z", "endDate": "2023-01-17T10:00:00Z"},
        }
    }

    from app.services.churchtools_client import _extract_appointment

    extracted = _extract_appointment(raw)
    result = parse_appointment(extracted)

    assert result.id == "1_103"
    assert result.title == "Nested Event"


@patch("app.services.jpeg_generator.convert_from_bytes")
def test_handle_jpeg_generation(mock_convert):
    # Mock PDF to image conversion
    mock_image1 = MagicMock()
    mock_image2 = MagicMock()
    mock_convert.return_value = [mock_image1, mock_image2]

    # Mock image save method to write test data to BytesIO
    def mock_save(stream, format):
        stream.write(b"test image data")

    mock_image1.save.side_effect = mock_save
    mock_image2.save.side_effect = mock_save

    # Call the function with bytes input
    pdf_bytes = b"%PDF-1.4 fake pdf content"
    result = handle_jpeg_generation(pdf_bytes)

    # Check that convert_from_bytes was called with the pdf bytes
    mock_convert.assert_called_once_with(pdf_bytes)

    # Check that the result is bytes (zip content)
    assert isinstance(result, bytes)


@pytest.mark.asyncio
@patch("app.api.appointments.load_background_image", return_value=(None, None))
@patch("app.api.appointments.load_logo", return_value=(None, None))
@patch("app.api.appointments.fetch_calendars")
@patch("app.api.appointments.get_date_range_from_form")
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
    context = call_args[1]

    assert call_args[0] == "appointments.html"
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
@patch("app.api.appointments.fetch_calendars")
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


SAMPLE_APPOINTMENT_DATA = [
    {
        "base": {
            "id": "1_101",
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
    mock_get_info.return_value = {"1_101": "Saved info"}

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


@pytest.mark.asyncio
async def test_fetch_appointments_deduplication(config_mock):
    """Same appointment appearing in multiple calendars should be deduplicated."""
    client = AsyncMock()

    def make_appointment():
        return {
            "base": {
                "id": "101",
                "title": "Shared Event",
                "address": {},
            },
            "calculated": {"startDate": "2023-01-15T10:00:00Z", "endDate": "2023-01-15T12:00:00Z"},
        }

    response1 = MagicMock()
    response1.status_code = 200
    response1.json.return_value = {"data": [make_appointment()]}

    response2 = MagicMock()
    response2.status_code = 200
    response2.json.return_value = {"data": [make_appointment()]}

    client.get.side_effect = [response1, response2]

    result = await fetch_appointments("token", "2023-01-15", "2023-01-16", [1, 2], client)

    # Same base ID in different calendars -> different composite IDs, both kept
    assert len(result) == 2
    ids = {r["base"]["id"] for r in result}
    assert "1_101" in ids
    assert "2_101" in ids


@pytest.mark.asyncio
async def test_fetch_appointments_partial_failure(config_mock):
    """If one calendar fails, appointments from other calendars should still be returned."""
    client = AsyncMock()

    success_response = MagicMock()
    success_response.status_code = 200
    success_response.json.return_value = {
        "data": [
            {
                "base": {"id": "101", "title": "Event 1", "address": {}},
                "calculated": {"startDate": "2023-01-15T10:00:00Z", "endDate": "2023-01-15T12:00:00Z"},
            }
        ]
    }

    fail_response = MagicMock()
    fail_response.status_code = 500

    client.get.side_effect = [success_response, fail_response]

    result = await fetch_appointments("token", "2023-01-15", "2023-01-16", [1, 2], client)

    assert len(result) == 1
    assert result[0]["base"]["id"] == "1_101"


# --- Tests for POST /api/generate (AJAX endpoint) ---


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
        appointment_ids=["1_101"],
        color_settings={
            "background_color": "#0000ff",
            "background_alpha": 100,
            "date_color": "#ff0000",
            "description_color": "#00ff00",
        },
        additional_infos={"1_101": "Extra info"},
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
    assert save_args[1] == [("1_101", "Extra info")]

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
        appointment_ids=["1_101"],
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
        appointment_ids=["1_101"],
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
        appointment_ids=["1_101"],
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
