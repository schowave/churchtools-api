import os
import io
from datetime import datetime
import pytz
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import Request, Form, File, UploadFile
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from app.api.appointments import (
    fetch_calendars, fetch_appointments, appointment_to_dict,
    get_date_range_from_form, handle_jpeg_generation,
    appointments_page, process_appointments, download_file
)
from app.config import Config

@pytest.fixture
def templates_mock():
    templates_mock = MagicMock(spec=Jinja2Templates)
    with patch('app.api.appointments.templates', templates_mock):
        yield templates_mock

@pytest.fixture
def config_mock():
    config_mock = {
        'CHURCHTOOLS_BASE': 'test.church.tools',
        'CHURCHTOOLS_BASE_URL': 'https://test.church.tools',
        'FILE_DIRECTORY': '/tmp/test_files'
    }
    with patch.multiple('app.api.appointments.Config',
                      CHURCHTOOLS_BASE=config_mock['CHURCHTOOLS_BASE'],
                      CHURCHTOOLS_BASE_URL=config_mock['CHURCHTOOLS_BASE_URL'],
                      FILE_DIRECTORY=config_mock['FILE_DIRECTORY']):
        # Ensure test directory exists
        os.makedirs(config_mock['FILE_DIRECTORY'], exist_ok=True)
        yield config_mock

@pytest.mark.asyncio
@patch('httpx.AsyncClient')
async def test_fetch_calendars_success(mock_client, config_mock):
    # Mock httpx client and response
    client_instance = AsyncMock()
    mock_client.return_value.__aenter__.return_value = client_instance
    
    # Mock successful response
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        'data': [
            {'id': 1, 'name': 'Calendar 1', 'isPublic': True},
            {'id': 2, 'name': 'Calendar 2', 'isPublic': False},
            {'id': 3, 'name': 'Calendar 3', 'isPublic': True}
        ]
    }
    client_instance.get.return_value = response
    
    # Call the function
    result = await fetch_calendars('test_token')
    
    # Check that client.get was called with correct parameters
    client_instance.get.assert_called_once_with(
        f'{config_mock["CHURCHTOOLS_BASE_URL"]}/api/calendars',
        headers={'Authorization': 'Login test_token'}
    )
    
    # Check that only public calendars were returned
    assert len(result) == 2
    assert result[0]['id'] == 1
    assert result[1]['id'] == 3

@pytest.mark.asyncio
@patch('httpx.AsyncClient')
async def test_fetch_calendars_error(mock_client):
    # Mock httpx client and response
    client_instance = AsyncMock()
    mock_client.return_value.__aenter__.return_value = client_instance
    
    # Mock error response
    response = MagicMock()
    response.status_code = 401
    response.raise_for_status.side_effect = Exception("Unauthorized")
    client_instance.get.return_value = response
    
    # Call the function and check that it raises the exception
    with pytest.raises(Exception):
        await fetch_calendars('invalid_token')

@pytest.mark.asyncio
@patch('httpx.AsyncClient')
async def test_fetch_appointments(mock_client, config_mock):
    # Mock httpx client and response
    client_instance = AsyncMock()
    mock_client.return_value.__aenter__.return_value = client_instance
    
    # Mock successful responses for two calendars
    response1 = MagicMock()
    response1.status_code = 200
    response1.json.return_value = {
        'data': [
            {
                'base': {
                    'id': '101',
                    'caption': 'Event 1',
                    'information': 'Info 1',
                    'address': {'meetingAt': 'Location 1'}
                },
                'calculated': {
                    'startDate': '2023-01-15T10:00:00Z',
                    'endDate': '2023-01-15T12:00:00Z'
                }
            }
        ]
    }
    
    response2 = MagicMock()
    response2.status_code = 200
    response2.json.return_value = {
        'data': [
            {
                'base': {
                    'id': '102',
                    'caption': 'Event 2',
                    'information': 'Info 2',
                    'address': {'meetingAt': 'Location 2'}
                },
                'calculated': {
                    'startDate': '2023-01-16T14:00:00Z',
                    'endDate': '2023-01-16T16:00:00Z'
                }
            }
        ]
    }
    
    # Set up client to return different responses for different calendar IDs
    client_instance.get.side_effect = [response1, response2]
    
    # Call the function
    result = await fetch_appointments('test_token', '2023-01-15', '2023-01-16', [1, 2])
    
    # Check that client.get was called twice with correct parameters
    assert client_instance.get.call_count == 2
    client_instance.get.assert_any_call(
        f'{config_mock["CHURCHTOOLS_BASE_URL"]}/api/calendars/1/appointments',
        headers={'Authorization': 'Login test_token'},
        params={'from': '2023-01-15', 'to': '2023-01-16'}
    )
    client_instance.get.assert_any_call(
        f'{config_mock["CHURCHTOOLS_BASE_URL"]}/api/calendars/2/appointments',
        headers={'Authorization': 'Login test_token'},
        params={'from': '2023-01-15', 'to': '2023-01-16'}
    )
    
    # Check that appointments were returned and IDs were modified
    assert len(result) == 2
    assert result[0]['base']['id'] == '1_101'
    assert result[1]['base']['id'] == '2_102'

def test_appointment_to_dict():
    # Test appointment with all fields
    appointment = {
        'base': {
            'id': '1_101',
            'caption': 'Test Event',
            'information': 'Test Info',
            'address': {'meetingAt': 'Test Location'}
        },
        'calculated': {
            'startDate': '2023-01-15T10:00:00Z',
            'endDate': '2023-01-15T12:00:00Z'
        }
    }
    
    result = appointment_to_dict(appointment)
    
    # Check that all fields were correctly mapped
    assert result['id'] == '1_101'
    assert result['description'] == 'Test Event'
    assert result['startDate'] == '2023-01-15T10:00:00Z'
    assert result['endDate'] == '2023-01-15T12:00:00Z'
    assert result['information'] == 'Test Info'
    assert result['meetingAt'] == 'Test Location'
    assert result['startDateView'] == '15.01.2023'
    assert result['startTimeView'] == '11:00'  # UTC+1 for Berlin
    assert result['endTimeView'] == '13:00'    # UTC+1 for Berlin
    assert result['additional_info'] == ""
    
    # Test appointment with missing address
    appointment = {
        'base': {
            'id': '1_102',
            'caption': 'Test Event 2',
            'information': 'Test Info 2',
            'address': None
        },
        'calculated': {
            'startDate': '2023-01-16T14:00:00Z',
            'endDate': '2023-01-16T16:00:00Z'
        }
    }
    
    result = appointment_to_dict(appointment)
    
    # Check that meetingAt is empty when address is None
    assert result['meetingAt'] == ''

@patch('app.api.appointments.convert_from_path')
def test_handle_jpeg_generation(mock_convert, config_mock):
    # Mock PDF to image conversion
    mock_image1 = MagicMock()
    mock_image2 = MagicMock()
    mock_convert.return_value = [mock_image1, mock_image2]
    
    # Mock image save method to write test data to BytesIO
    def mock_save(stream, format):
        stream.write(b'test image data')
    mock_image1.save.side_effect = mock_save
    mock_image2.save.side_effect = mock_save
    
    # Call the function
    result = handle_jpeg_generation('test.pdf')
    
    # Check that convert_from_path was called with correct path
    mock_convert.assert_called_once_with(os.path.join(config_mock['FILE_DIRECTORY'], 'test.pdf'))
    
    # Check that the result is a string containing the ZIP file path
    assert isinstance(result, str)
    assert result.endswith('.zip')
    
    # We could further test the ZIP file contents, but that would require more complex setup

@pytest.mark.asyncio
@patch('app.api.appointments.fetch_calendars')
@patch('app.api.appointments.get_date_range_from_form')
@patch('app.api.appointments.load_color_settings')
async def test_appointments_page_with_token(mock_load_color, mock_get_date, mock_fetch, templates_mock, config_mock):
    # Mock request with login_token
    request_mock = MagicMock(spec=Request)
    request_mock.cookies.get.return_value = "test_token"
    
    # Mock database session
    db_mock = MagicMock()
    
    # Mock return values
    mock_get_date.return_value = ('2023-01-15', '2023-01-22')
    mock_fetch.return_value = [
        {'id': 1, 'name': 'Calendar 1'},
        {'id': 2, 'name': 'Calendar 2'}
    ]
    mock_load_color.return_value = {
        'name': 'default',
        'background_color': '#ffffff',
        'background_alpha': 128,
        'date_color': '#c1540c',
        'description_color': '#4e4e4e'
    }
    
    # Call the function
    result = await appointments_page(request_mock, db_mock)
    
    # Check that fetch_calendars was called with the token
    mock_fetch.assert_called_once_with("test_token")
    
    # Check that templates.TemplateResponse was called with correct parameters
    templates_mock.TemplateResponse.assert_called_once()
    call_args = templates_mock.TemplateResponse.call_args[0]
    context = call_args[1]
    
    assert call_args[0] == "appointments.html"
    # Check that all expected keys are present in the template context
    assert 'calendars' in context
    assert 'selected_calendar_ids' in context
    assert 'start_date' in context
    assert 'end_date' in context
    assert 'base_url' in context
    assert 'color_settings' in context
    assert context['calendars'] == mock_fetch.return_value
    assert context['selected_calendar_ids'] == ['1', '2']
    assert context['start_date'] == '2023-01-15'
    assert context['end_date'] == '2023-01-22'
    assert context['base_url'] == config_mock['CHURCHTOOLS_BASE']
    assert context['color_settings'] == mock_load_color.return_value

@pytest.mark.asyncio
@patch('app.api.appointments.fetch_calendars')
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
    assert result.headers['location'] == '/'
    
    # Check that fetch_calendars was not called
    mock_fetch.assert_not_called()

@pytest.mark.asyncio
async def test_download_file_success(config_mock):
    # Create a test file
    test_file_path = os.path.join(config_mock['FILE_DIRECTORY'], 'test.txt')
    with open(test_file_path, 'w') as f:
        f.write('Test content')
    
    # Call the function
    result = await download_file('test.txt')
    
    # Check that the result is a FileResponse
    assert isinstance(result, FileResponse)
    assert result.path == test_file_path
    assert result.filename == 'test.txt'
    
    # Clean up
    os.remove(test_file_path)

@pytest.mark.asyncio
async def test_download_file_not_found():
    # Call the function with a non-existent file
    with pytest.raises(Exception) as context:
        await download_file('nonexistent.txt')
    
    # Check that the correct exception was raised
    assert context.value.status_code == 404
    assert context.value.detail == 'File not found'

if __name__ == '__main__':
    unittest.main()