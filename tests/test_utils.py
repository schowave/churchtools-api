import pytest
from unittest.mock import patch, MagicMock
import sqlite3
from datetime import datetime, timezone
from tests.conftest import TestConfig
from config import Config


class TestUtils:
    def test_parse_iso_datetime(self, app_context):
        from app.utils import parse_iso_datetime
        
        dt = parse_iso_datetime('2023-01-01T10:00:00Z')
        assert dt.year == 2023
        assert dt.month == 1
        assert dt.day == 1
        
        dt = parse_iso_datetime('2023-01-01T10:00:00')
        assert dt.year == 2023
        assert dt.month == 1
        assert dt.day == 1
        
        dt = parse_iso_datetime('2023-01-01T10:00:00+01:00')
        assert dt.year == 2023
        assert dt.month == 1
        assert dt.day == 1
        assert dt.tzinfo is not None
        
        dt = parse_iso_datetime('2023-01-01T10:00:00-05:00')
        assert dt.year == 2023
        assert dt.month == 1
        assert dt.day == 1
        assert dt.tzinfo is not None

    def test_normalize_newlines(self, app_context):
        from app.utils import normalize_newlines
        
        text = "Line 1\r\nLine 2\r\nLine 3"
        normalized = normalize_newlines(text)
        assert normalized == "Line 1\nLine 2\nLine 3"
        
        text = "Line 1\nLine 2\nLine 3"
        normalized = normalize_newlines(text)
        assert normalized == "Line 1\nLine 2\nLine 3"
        
        text = "Line 1\r\nLine 2\nLine 3"
        normalized = normalize_newlines(text)
        assert normalized == "Line 1\nLine 2\nLine 3"
        
        text = ""
        normalized = normalize_newlines(text)
        assert normalized == ""
        
        text = "This is a text without line breaks."
        normalized = normalize_newlines(text)
        assert normalized == text
        
        text = "Line 1\r\nLine 2\r\nLine 3"
        normalized = normalize_newlines(text)
        assert normalized == "Line 1\nLine 2\nLine 3"
        
        text = "Line 1\nLine 2\nLine 3"
        normalized = normalize_newlines(text)
        assert normalized == "Line 1\nLine 2\nLine 3"
        
        text = "Line 1\r\nLine 2\nLine 3\r\nLine 4"
        normalized = normalize_newlines(text)
        assert normalized == "Line 1\nLine 2\nLine 3\nLine 4"

    def test_appointment_to_dict(self, app_context):
        from app.utils import appointment_to_dict
        
        appointment = {
            'base': {
                'id': '1_123',
                'caption': 'Test Appointment',
                'information': 'Test Info',
                'address': {'meetingAt': 'Test Location'}
            },
            'calculated': {
                'startDate': '2023-01-01T10:00:00Z',
                'endDate': '2023-01-01T11:00:00Z'
            }
        }
        
        result = appointment_to_dict(appointment)
        
        assert result['id'] == '1_123'
        assert result['description'] == 'Test Appointment'
        assert result['startDate'] == '2023-01-01T10:00:00Z'
        assert result['endDate'] == '2023-01-01T11:00:00Z'
        assert result['information'] == 'Test Info'
        assert result['meetingAt'] == 'Test Location'
        assert result['startDateView'] == '01.01.2023'
        assert 'startTimeView' in result
        assert 'endTimeView' in result
        assert result['additional_info'] == ""
        
        appointment = {
            'base': {
                'id': '1_123',
                'caption': 'Test Appointment',
                'information': '',
                'address': {'meetingAt': ''}
            },
            'calculated': {
                'startDate': '2023-01-01T10:00:00Z',
                'endDate': '2023-01-01T11:00:00Z'
            }
        }
        
        result = appointment_to_dict(appointment)
        
        assert result['id'] == '1_123'
        assert result['description'] == 'Test Appointment'
        assert result['startDate'] == '2023-01-01T10:00:00Z'
        assert result['endDate'] == '2023-01-01T11:00:00Z'
        assert result['information'] == ""
        assert result['meetingAt'] == ""
        assert result['startDateView'] == '01.01.2023'
        assert 'startTimeView' in result
        assert 'endTimeView' in result
        assert result['additional_info'] == ""

    @patch('app.utils.requests.get')
    def test_fetch_calendars(self, mock_get, app_context):
        from app.utils import fetch_calendars
        
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            'data': [
                {'id': 1, 'name': 'Calendar 1', 'isPublic': True},
                {'id': 2, 'name': 'Calendar 2', 'isPublic': True},
                {'id': 3, 'name': 'Calendar 3', 'isPublic': False}
            ]
        }
        mock_get.return_value = mock_response
        
        calendars = fetch_calendars('test-login-token')
        
        assert len(calendars) == 2
        assert calendars[0]['id'] == 1
        assert calendars[1]['id'] == 2
        
        mock_get.assert_called_once_with(
            f'{TestConfig.CHURCHTOOLS_BASE_URL}/api/calendars',
            headers={'Authorization': 'Login test-login-token'}
        )
        
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {'data': []}
        mock_get.return_value = mock_response
        
        calendars = fetch_calendars('test-login-token')
        
        assert len(calendars) == 0
        
        mock_response = MagicMock()
        mock_response.ok = False
        mock_get.return_value = mock_response
        
        calendars = fetch_calendars('test-login-token')
        
        assert calendars is None or len(calendars) == 0

    @patch('app.utils.requests.get')
    def test_fetch_appointments(self, mock_get, app_context):
        from app.utils import fetch_appointments
        
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            'data': [
                {
                    'base': {
                        'id': '123',
                        'caption': 'Test Appointment 1',
                        'information': 'Test Info 1',
                        'address': {'meetingAt': 'Test Location 1'}
                    },
                    'calculated': {
                        'startDate': '2023-01-01T10:00:00Z',
                        'endDate': '2023-01-01T11:00:00Z'
                    }
                },
                {
                    'base': {
                        'id': '123',
                        'caption': 'Test Appointment 2',
                        'information': 'Test Info 2',
                        'address': {'meetingAt': 'Test Location 2'}
                    },
                    'calculated': {
                        'startDate': '2023-01-02T10:00:00Z',
                        'endDate': '2023-01-02T11:00:00Z'
                    }
                }
            ]
        }
        mock_get.return_value = mock_response
        
        appointments = fetch_appointments('test-login-token', '2023-01-01', '2023-01-31', [1])
        
        assert len(appointments) == 2
        assert appointments[0]['base']['id'] == '1_123'
        assert appointments[1]['base']['id'] == '1_123_1'
        
        mock_get.assert_called_once_with(
            f'{TestConfig.CHURCHTOOLS_BASE_URL}/api/calendars/1/appointments',
            headers={'Authorization': 'Login test-login-token'},
            params={'from': '2023-01-01', 'to': '2023-01-31'}
        )
        
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {'data': []}
        mock_get.return_value = mock_response
        
        appointments = fetch_appointments('test-login-token', '2023-01-01', '2023-01-31', [1])
        
        assert len(appointments) == 0
        
        mock_response = MagicMock()
        mock_response.ok = False
        mock_get.return_value = mock_response
        
        appointments = fetch_appointments('test-login-token', '2023-01-01', '2023-01-31', [1])
        
        assert len(appointments) == 0

    def test_additional_infos(self, app_context):
        from app.utils import save_additional_infos, get_additional_infos
        from app import create_schema
        
        create_schema()
        
        appointment_info_list = [
            ('1_123', 'Additional Info 1'),
            ('1_456', 'Additional Info 2')
        ]
        save_additional_infos(appointment_info_list)
        
        infos = get_additional_infos(['1_123', '1_456', '1_789'])
        
        assert '1_123' in infos
        assert '1_456' in infos
        assert infos['1_123'] == 'Additional Info 1'
        assert infos['1_456'] == 'Additional Info 2'
        
        infos = get_additional_infos([])
        
        assert len(infos) == 0
        
        appointment_info_list = [
            ('1_123', 'New Additional Info 1'),
            ('1_789', 'Additional Info 3')
        ]
        save_additional_infos(appointment_info_list)
        
        infos = get_additional_infos(['1_123', '1_456', '1_789'])
        
        assert len(infos) >= 3
        assert infos['1_123'] == 'New Additional Info 1'
        assert infos['1_456'] == 'Additional Info 2'
        assert infos['1_789'] == 'Additional Info 3'

    def test_color_settings(self, app_context):
        from app.utils import save_color_settings, load_color_settings
        from app import create_schema
        
        create_schema()
        
        settings = {
            'name': 'test',
            'background_color': '#ffffff',
            'background_alpha': 128,
            'date_color': '#c1540c',
            'description_color': '#4e4e4e'
        }
        save_color_settings(settings)
        
        loaded_settings = load_color_settings('test')
        
        assert loaded_settings['name'] == 'test'
        assert loaded_settings['background_color'] == '#ffffff'
        assert loaded_settings['background_alpha'] == 128
        assert loaded_settings['date_color'] == '#c1540c'
        assert loaded_settings['description_color'] == '#4e4e4e'
        
        default_settings = load_color_settings('non_existent')
        
        assert default_settings['name'] == 'non_existent'
        assert default_settings['background_color'] == '#ffffff'
        assert default_settings['background_alpha'] == 128
        assert default_settings['date_color'] == '#c1540c'
        assert default_settings['description_color'] == '#4e4e4e'
        
        settings = {
            'name': 'test',
            'background_color': '#000000',
            'background_alpha': 64,
            'date_color': '#ff0000',
            'description_color': '#00ff00'
        }
        save_color_settings(settings)
        
        loaded_settings = load_color_settings('test')
        
        assert loaded_settings['name'] == 'test'
        assert loaded_settings['background_color'] == '#000000'
        assert loaded_settings['background_alpha'] == 64
        assert loaded_settings['date_color'] == '#ff0000'
        assert loaded_settings['description_color'] == '#00ff00'