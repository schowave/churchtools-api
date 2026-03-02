import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.api.appointments import appointments_page, download_file, process_appointments
from app.schemas import AppointmentData, ColorSettings
from app.services.churchtools_client import AuthenticationError, fetch_appointments, fetch_calendars, parse_appointment
from app.services.jpeg_generator import handle_jpeg_generation


@pytest.fixture
def templates_mock():
    templates_mock = MagicMock(spec=Jinja2Templates)
    with patch("app.api.appointments.templates", templates_mock):
        yield templates_mock


@pytest.fixture
def config_mock():
    config_mock = {
        "CHURCHTOOLS_BASE": "test.church.tools",
        "CHURCHTOOLS_BASE_URL": "https://test.church.tools",
        "FILE_DIRECTORY": "/tmp/test_files",
    }
    with patch.multiple(
        "app.config.Config",
        CHURCHTOOLS_BASE=config_mock["CHURCHTOOLS_BASE"],
        CHURCHTOOLS_BASE_URL=config_mock["CHURCHTOOLS_BASE_URL"],
        FILE_DIRECTORY=config_mock["FILE_DIRECTORY"],
    ):
        # Ensure test directory exists
        os.makedirs(config_mock["FILE_DIRECTORY"], exist_ok=True)
        yield config_mock


@pytest.mark.asyncio
@patch("httpx.AsyncClient")
async def test_fetch_calendars_success(mock_client, config_mock):
    # Mock httpx client and response
    client_instance = AsyncMock()
    mock_client.return_value.__aenter__.return_value = client_instance

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
    client_instance.get.return_value = response

    # Call the function
    result = await fetch_calendars("test_token")

    # Check that client.get was called with correct parameters
    client_instance.get.assert_called_once_with(
        f"{config_mock['CHURCHTOOLS_BASE_URL']}/api/calendars", headers={"Authorization": "Login test_token"}
    )

    # Check that only public calendars were returned
    assert len(result) == 2
    assert result[0]["id"] == 1
    assert result[1]["id"] == 3


@pytest.mark.asyncio
@patch("httpx.AsyncClient")
async def test_fetch_calendars_auth_error(mock_client):
    # Mock httpx client and response
    client_instance = AsyncMock()
    mock_client.return_value.__aenter__.return_value = client_instance

    # Mock 401 response
    response = MagicMock()
    response.status_code = 401
    client_instance.get.return_value = response

    # Call the function and check that it raises AuthenticationError
    with pytest.raises(AuthenticationError):
        await fetch_calendars("invalid_token")


@pytest.mark.asyncio
@patch("httpx.AsyncClient")
async def test_fetch_appointments(mock_client, config_mock):
    # Mock httpx client and response
    client_instance = AsyncMock()
    mock_client.return_value.__aenter__.return_value = client_instance

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
    client_instance.get.side_effect = [response1, response2]

    # Call the function
    result = await fetch_appointments("test_token", "2023-01-15", "2023-01-16", [1, 2])

    # Check that client.get was called twice with correct parameters
    assert client_instance.get.call_count == 2
    client_instance.get.assert_any_call(
        f"{config_mock['CHURCHTOOLS_BASE_URL']}/api/calendars/1/appointments",
        headers={"Authorization": "Login test_token"},
        params={"from": "2023-01-15", "to": "2023-01-16"},
    )
    client_instance.get.assert_any_call(
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


@patch("app.services.jpeg_generator.convert_from_path")
def test_handle_jpeg_generation(mock_convert, config_mock):
    # Mock PDF to image conversion
    mock_image1 = MagicMock()
    mock_image2 = MagicMock()
    mock_convert.return_value = [mock_image1, mock_image2]

    # Mock image save method to write test data to BytesIO
    def mock_save(stream, format):
        stream.write(b"test image data")

    mock_image1.save.side_effect = mock_save
    mock_image2.save.side_effect = mock_save

    # Call the function
    result = handle_jpeg_generation("test.pdf")

    # Check that convert_from_path was called with correct path
    mock_convert.assert_called_once_with(os.path.join(config_mock["FILE_DIRECTORY"], "test.pdf"))

    # Check that the result is a string containing the ZIP file path
    assert isinstance(result, str)
    assert result.endswith(".zip")

    # We could further test the ZIP file contents, but that would require more complex setup


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

    # Mock return values
    mock_get_date.return_value = ("2023-01-15", "2023-01-22")
    mock_fetch_cal.return_value = [{"id": 1, "name": "Calendar 1"}, {"id": 2, "name": "Calendar 2"}]
    mock_load_color.return_value = ColorSettings(name="default")

    # Call the function (page renders without appointments, AJAX loads them later)
    await appointments_page(request_mock, db_mock, start_date=None, end_date=None, calendar_ids=None)

    # Check that fetch_calendars was called with the token
    mock_fetch_cal.assert_called_once_with("test_token")

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

    # Call the function
    result = await appointments_page(request_mock, db_mock)

    # Check that the result is a RedirectResponse
    assert isinstance(result, RedirectResponse)
    assert result.status_code == 303
    assert result.headers["location"] == "/"

    # Check that fetch_calendars was not called
    mock_fetch.assert_not_called()


@pytest.mark.asyncio
async def test_download_file_success(config_mock):
    # Create a test file
    test_file_path = os.path.join(config_mock["FILE_DIRECTORY"], "test.txt")
    with open(test_file_path, "w") as f:
        f.write("Test content")

    # Call the function
    result = await download_file("test.txt")

    # Check that the result is a FileResponse
    assert isinstance(result, FileResponse)
    assert result.path == test_file_path
    assert result.filename == "test.txt"

    # Clean up
    os.remove(test_file_path)


@pytest.mark.asyncio
async def test_download_file_not_found():
    # Call the function with a non-existent file
    with pytest.raises(Exception) as context:
        await download_file("nonexistent.txt")

    # Check that the correct exception was raised
    assert context.value.status_code == 404
    assert context.value.detail == "File not found"


# --- Tests for process_appointments (4.1) ---

SAMPLE_CALENDARS = [
    {"id": 1, "name": "Calendar 1"},
    {"id": 2, "name": "Calendar 2"},
]

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


def _make_request_mock(has_token=True):
    """Create a mock Request with cookies and async form()."""
    request = MagicMock(spec=Request)
    request.cookies.get.return_value = "test_token" if has_token else None

    # Mock the async form() method used by _prepare_selected_appointments
    form_data = MagicMock()
    form_data.get.return_value = ""

    async def async_form():
        return form_data

    request.form = async_form

    return request


@pytest.mark.asyncio
@patch("app.api.appointments.fetch_calendars")
async def test_process_appointments_no_token(mock_fetch, templates_mock):
    """POST without login token should redirect to login."""
    request = _make_request_mock(has_token=False)
    db = MagicMock()

    result = await process_appointments(
        request=request,
        db=db,
        generate_pdf_btn=None,
        generate_jpeg_btn=None,
        start_date="2023-01-15",
        end_date="2023-01-22",
        calendar_ids=None,
        appointment_id=None,
        date_color=None,
        description_color=None,
        background_color=None,
        alpha=None,
    )

    assert isinstance(result, RedirectResponse)
    assert result.status_code == 303
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

    mock_fetch_app.return_value = SAMPLE_APPOINTMENT_DATA
    mock_get_info.return_value = {"1_101": "Saved info"}

    response = await api_appointments(
        request=request,
        db=db,
        start_date="2023-01-15",
        end_date="2023-01-22",
        calendar_ids=["1", "2"],
    )

    assert response.status_code == 200
    mock_fetch_app.assert_called_once_with("test_token", "2023-01-15", "2023-01-22", [1, 2])


@pytest.mark.asyncio
@patch("app.api.appointments.load_background_image", return_value=(None, None))
@patch("app.api.appointments.load_logo", return_value=(None, None))
@patch("app.api.appointments.create_pdf")
@patch("app.api.appointments.save_color_settings")
@patch("app.api.appointments.save_additional_infos")
@patch("app.api.appointments.load_color_settings")
@patch("app.api.appointments.fetch_appointments")
@patch("app.api.appointments.fetch_calendars")
async def test_process_appointments_generate_pdf(
    mock_fetch_cal,
    mock_fetch_app,
    mock_load_color,
    mock_save_info,
    mock_save_color,
    mock_create_pdf,
    mock_load_logo,
    mock_load_bg,
    templates_mock,
    config_mock,
):
    """Clicking 'generate PDF' should create PDF and redirect to download."""
    request = _make_request_mock()
    db = MagicMock()

    mock_fetch_cal.return_value = SAMPLE_CALENDARS
    mock_fetch_app.return_value = SAMPLE_APPOINTMENT_DATA
    mock_load_color.return_value = ColorSettings(name="default")
    mock_create_pdf.return_value = "2023-01-15_Termine.pdf"

    result = await process_appointments(
        request=request,
        db=db,
        generate_pdf_btn="PDF Generieren",
        generate_jpeg_btn=None,
        start_date="2023-01-15",
        end_date="2023-01-22",
        calendar_ids=["1"],
        appointment_id=["1_101"],
        date_color="#ff0000",
        description_color="#00ff00",
        background_color="#0000ff",
        alpha=100,
    )

    # Should be a redirect to the download URL
    assert isinstance(result, RedirectResponse)
    assert result.status_code == 303
    assert "/download/2023-01-15_Termine.pdf" in result.headers["location"]

    # create_pdf should be called with overridden color values
    mock_create_pdf.assert_called_once()
    call_args = mock_create_pdf.call_args
    assert call_args[0][1] == "#ff0000"  # date_color
    assert call_args[0][2] == "#0000ff"  # background_color
    assert call_args[0][3] == "#00ff00"  # description_color
    assert call_args[0][4] == 100  # alpha


@pytest.mark.asyncio
@patch("app.api.appointments.load_color_settings")
@patch("app.api.appointments.fetch_calendars")
async def test_process_appointments_generate_pdf_no_selection(
    mock_fetch_cal, mock_load_color, templates_mock, config_mock
):
    """Generate PDF with no appointments selected should show error."""
    request = _make_request_mock()
    db = MagicMock()

    mock_fetch_cal.return_value = SAMPLE_CALENDARS
    mock_load_color.return_value = ColorSettings(name="default")

    await process_appointments(
        request=request,
        db=db,
        generate_pdf_btn="PDF Generieren",
        generate_jpeg_btn=None,
        start_date="2023-01-15",
        end_date="2023-01-22",
        calendar_ids=["1"],
        appointment_id=None,
        date_color=None,
        description_color=None,
        background_color=None,
        alpha=None,
    )

    # Should render template with error message
    templates_mock.TemplateResponse.assert_called_once()
    context = templates_mock.TemplateResponse.call_args[0][1]
    assert "error" in context


@pytest.mark.asyncio
@patch("app.api.appointments.load_background_image", return_value=(None, None))
@patch("app.api.appointments.load_logo", return_value=(None, None))
@patch("app.api.appointments.handle_jpeg_generation")
@patch("app.api.appointments.create_pdf")
@patch("app.api.appointments.save_color_settings")
@patch("app.api.appointments.save_additional_infos")
@patch("app.api.appointments.load_color_settings")
@patch("app.api.appointments.fetch_appointments")
@patch("app.api.appointments.fetch_calendars")
async def test_process_appointments_generate_jpeg(
    mock_fetch_cal,
    mock_fetch_app,
    mock_load_color,
    mock_save_info,
    mock_save_color,
    mock_create_pdf,
    mock_jpeg,
    mock_load_logo,
    mock_load_bg,
    templates_mock,
    config_mock,
):
    """Clicking 'generate JPEG' should create PDF, convert to JPEG ZIP, and return file."""
    request = _make_request_mock()
    db = MagicMock()

    mock_fetch_cal.return_value = SAMPLE_CALENDARS
    mock_fetch_app.return_value = SAMPLE_APPOINTMENT_DATA
    mock_load_color.return_value = ColorSettings(name="default")
    mock_create_pdf.return_value = "2023-01-15_Termine.pdf"
    mock_jpeg.return_value = "2023-01-15_Termine.zip"

    # Create the expected zip file so FileResponse doesn't fail
    zip_path = os.path.join(config_mock["FILE_DIRECTORY"], "2023-01-15_Termine.zip")
    with open(zip_path, "wb") as f:
        f.write(b"fake zip")

    result = await process_appointments(
        request=request,
        db=db,
        generate_pdf_btn=None,
        generate_jpeg_btn="JPEG generieren",
        start_date="2023-01-15",
        end_date="2023-01-22",
        calendar_ids=["1"],
        appointment_id=["1_101"],
        date_color=None,
        description_color=None,
        background_color=None,
        alpha=None,
    )

    assert isinstance(result, FileResponse)
    mock_create_pdf.assert_called_once()
    mock_jpeg.assert_called_once_with("2023-01-15_Termine.pdf")

    # Clean up
    os.remove(zip_path)


@pytest.mark.asyncio
@patch("app.api.appointments.load_background_image", return_value=(None, None))
@patch("app.api.appointments.load_logo", return_value=(None, None))
@patch("app.api.appointments.load_color_settings")
@patch("app.api.appointments.fetch_calendars")
async def test_process_appointments_default_form(
    mock_fetch_cal, mock_load_color, mock_load_logo, mock_load_bg, templates_mock, config_mock
):
    """POST with no button pressed should render the default form."""
    request = _make_request_mock()
    db = MagicMock()

    mock_fetch_cal.return_value = SAMPLE_CALENDARS
    mock_load_color.return_value = ColorSettings(name="default")

    await process_appointments(
        request=request,
        db=db,
        generate_pdf_btn=None,
        generate_jpeg_btn=None,
        start_date="2023-01-15",
        end_date="2023-01-22",
        calendar_ids=None,
        appointment_id=None,
        date_color=None,
        description_color=None,
        background_color=None,
        alpha=None,
    )

    templates_mock.TemplateResponse.assert_called_once()
    context = templates_mock.TemplateResponse.call_args[0][1]
    assert context["calendars"] == SAMPLE_CALENDARS
    # No calendars selected, should use all available
    assert context["selected_calendar_ids"] is None


@pytest.mark.asyncio
@patch("app.api.appointments.load_background_image", return_value=(None, None))
@patch("app.api.appointments.load_logo", return_value=(None, None))
@patch("app.api.appointments.load_color_settings")
@patch("app.api.appointments.get_date_range_from_form")
@patch("app.api.appointments.fetch_calendars")
async def test_process_appointments_default_dates(
    mock_fetch_cal, mock_get_dates, mock_load_color, mock_load_logo, mock_load_bg, templates_mock, config_mock
):
    """When no dates provided, should fall back to get_date_range_from_form()."""
    request = _make_request_mock()
    db = MagicMock()

    mock_fetch_cal.return_value = SAMPLE_CALENDARS
    mock_load_color.return_value = ColorSettings(name="default")
    mock_get_dates.return_value = ("2023-02-01", "2023-02-08")

    await process_appointments(
        request=request,
        db=db,
        generate_pdf_btn=None,
        generate_jpeg_btn=None,
        start_date=None,
        end_date=None,
        calendar_ids=None,
        appointment_id=None,
        date_color=None,
        description_color=None,
        background_color=None,
        alpha=None,
    )

    # Default dates should be used in template context
    context = templates_mock.TemplateResponse.call_args[0][1]
    assert context["start_date"] == "2023-02-01"
    assert context["end_date"] == "2023-02-08"
