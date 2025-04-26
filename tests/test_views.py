import pytest
from unittest.mock import patch, MagicMock, mock_open
import os
from io import BytesIO
import zipfile
from tests.conftest import TestConfig
from config import Config


class TestViews:
    """Tests for the application views."""

    def test_login_page_loads(self, client):
        """Test if the login page loads."""
        response = client.get('/')
        assert response.status_code == 200
        assert b'API-Zugriff' in response.data  # This is part of the HTML content, not a test comment
        assert b'Login' in response.data

    @patch('app.views.requests.post')
    @patch('app.views.requests.get')
    def test_login_success(self, mock_get, mock_post, client):
        """Test for successful login."""
        # Mock for POST request to login
        mock_post_response = MagicMock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = {
            'data': {'personId': 123}
        }
        mock_post_response.cookies = {'session': 'test-session'}
        mock_post.return_value = mock_post_response
        
        # Mock for GET request to token
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {
            'data': 'test-login-token'
        }
        mock_get.return_value = mock_get_response
        
        # Send login request
        response = client.post('/', data={
            'username': 'testuser',
            'password': 'testpassword'
        }, follow_redirects=True)
        
        # Check if redirected to overview page
        assert response.status_code == 200
        assert b'Termin' in response.data  # This is part of the HTML content, not a test comment
        
        # Check if the correct API calls were made
        mock_post.assert_called_once_with(
            f'{TestConfig.CHURCHTOOLS_BASE_URL}/api/login',
            json={"password": "testpassword", "rememberMe": True, "username": "testuser"}
        )
        mock_get.assert_called_once_with(
            f'{TestConfig.CHURCHTOOLS_BASE_URL}/api/persons/123/logintoken',
            cookies=mock_post_response.cookies
        )

    @patch('app.views.requests.post')
    def test_login_failure(self, mock_post, client):
        """Test for failed login."""
        # Mock for failed POST request
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response
        
        # Send login request
        response = client.post('/', data={
            'username': 'wronguser',
            'password': 'wrongpassword'
        }, follow_redirects=True)
        
        # Check if staying on login page
        assert response.status_code == 200
        assert b'Login' in response.data
        assert b'Invalid username or password' in response.data

    @patch('app.views.make_response')
    def test_logout(self, mock_make_response, client):
        """Test for logout functionality."""
        # Mock for make_response
        mock_response = MagicMock()
        mock_response.set_cookie = MagicMock()
        mock_make_response.return_value = mock_response
        
        # First set a cookie to simulate a logged-in state
        with client.session_transaction() as session:
            session['login_token'] = 'test-login-token'
        
        # Send logout request
        response = client.post('/logout')
        
        # Check if set_cookie was called to delete the cookie
        mock_response.set_cookie.assert_called_with('login_token', '', expires=0)
        
        # Check if redirected to login page when trying to access
        # a protected route
        response = client.get('/overview', follow_redirects=True)
        assert response.status_code == 200
        assert b'Login' in response.data

    def test_protected_routes_redirect_to_login(self, client):
        """Test if protected routes redirect to the login page when not logged in."""
        # Access overview page without login
        response = client.get('/overview', follow_redirects=True)
        assert response.status_code == 200
        assert b'Login' in response.data
        
        # Access appointments page without login
        response = client.get('/appointments', follow_redirects=True)
        assert response.status_code == 200
        assert b'Login' in response.data

    @patch('app.views.get_login_token')
    @patch('app.utils.get_login_token')
    @patch('app.utils.fetch_calendars')
    @patch('app.utils.requests.get')
    def test_appointments_page_with_login(self, mock_requests_get, mock_fetch_calendars,
                                         mock_utils_get_login_token, mock_views_get_login_token,
                                         client):
        """Test if the appointments page loads with login."""
        # Mock for login token
        mock_utils_get_login_token.return_value = 'test-login-token'
        mock_views_get_login_token.return_value = 'test-login-token'
        
        # Mock for requests.get
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            'data': [
                {'id': 1, 'name': 'Calendar 1', 'isPublic': True},
                {'id': 2, 'name': 'Calendar 2', 'isPublic': True}
            ]
        }
        mock_requests_get.return_value = mock_response
        
        # Mock for calendars
        mock_fetch_calendars.return_value = [
            {'id': 1, 'name': 'Calendar 1', 'isPublic': True},
            {'id': 2, 'name': 'Calendar 2', 'isPublic': True}
        ]
        
        # Set cookie for authentication
        with client.session_transaction() as session:
            session['login_token'] = 'test-login-token'
        
        # Access appointments page with login
        response = client.get('/appointments')
        assert response.status_code == 200
        assert b'Termin' in response.data  # This is part of the HTML content, not a test comment

    @patch('app.views.get_login_token')
    @patch('app.utils.get_login_token')
    @patch('app.utils.fetch_calendars')
    @patch('app.views.fetch_appointments')
    @patch('app.views.get_additional_infos')
    @patch('app.utils.requests.get')
    def test_fetch_appointments(self, mock_requests_get, mock_get_additional_infos,
                               mock_fetch_appointments, mock_fetch_calendars,
                               mock_utils_get_login_token, mock_views_get_login_token,
                               client):
        """Test for fetching appointments."""
        # Set up mocks
        mock_utils_get_login_token.return_value = 'test-login-token'
        mock_views_get_login_token.return_value = 'test-login-token'
        
        # Mock for requests.get
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            'data': [
                {'id': 1, 'name': 'Calendar 1', 'isPublic': True}
            ]
        }
        mock_requests_get.return_value = mock_response
        
        mock_fetch_calendars.return_value = [
            {'id': 1, 'name': 'Calendar 1', 'isPublic': True}
        ]
        
        # Mock for appointments
        mock_appointment = {
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
        mock_fetch_appointments.return_value = [mock_appointment]
        
        # Mock for additional info
        mock_get_additional_infos.return_value = {'1_123': 'Additional Info'}
        
        # Set cookie and request to fetch appointments
        with client.session_transaction() as session:
            session['selected_calendar_ids'] = ['1']
            session['login_token'] = 'test-login-token'
        
        response = client.post('/appointments', data={
            'start_date': '2023-01-01',
            'end_date': '2023-01-31',
            'calendar_ids': ['1'],
            'fetch_appointments': 'true'
        })
        
        assert response.status_code == 200
        assert b'Test Appointment' in response.data
        
    @patch('app.views.request', new_callable=MagicMock)
    @patch('app.views.normalize_newlines')
    @patch('app.views.save_additional_infos')
    def test_save_additional_infos_from_form(self, mock_save_additional_infos, mock_normalize_newlines, mock_request, request_context):
        from app.views import save_additional_infos_from_form
        
        mock_form = MagicMock()
        mock_form.get.side_effect = lambda key: f"Info for {key.split('_')[-1]}"
        mock_request.form = mock_form
        
        mock_normalize_newlines.side_effect = lambda text: text
        
        selected_appointment_ids = ['1_123', '1_456']
        save_additional_infos_from_form(selected_appointment_ids)
        
        assert mock_normalize_newlines.call_count == 2
        
        mock_save_additional_infos.assert_called_once()
        
        call_args = mock_save_additional_infos.call_args[0][0]
        assert len(call_args) == 2
        assert call_args[0][0] == '1_123'
        assert call_args[1][0] == '1_456'
        
    @patch('app.views.request', new_callable=MagicMock)
    @patch('app.views.fetch_appointments')
    @patch('app.views.appointment_to_dict')
    def test_get_and_process_appointments(self, mock_appointment_to_dict, mock_fetch_appointments, mock_request, request_context):
        from app.views import get_and_process_appointments
        
        mock_form = MagicMock()
        mock_form.getlist.return_value = ['1', '2']
        mock_request.form = mock_form
        
        mock_appointments = [
            {'base': {'id': '1_123'}},
            {'base': {'id': '2_456'}}
        ]
        mock_fetch_appointments.return_value = mock_appointments
        
        mock_appointment_to_dict.side_effect = lambda app: {'id': app['base']['id']}
        
        with patch('app.views.session') as mock_session:
            result = get_and_process_appointments('test-token', '2023-01-01', '2023-01-31')
            
            mock_fetch_appointments.assert_called_once_with('test-token', '2023-01-01', '2023-01-31', [1, 2])
            
            assert mock_appointment_to_dict.call_count == 2
            
            mock_session.__setitem__.assert_called_once_with('fetched_appointments', [
                {'id': '1_123'},
                {'id': '2_456'}
            ])
            
            assert result == mock_appointments
            
    @patch('app.views.session', new_callable=MagicMock)
    @patch('app.views.get_additional_infos')
    @patch('app.views.create_pdf')
    @patch('app.views.get_background_image_stream')
    def test_handle_pdf_generation(self, mock_get_background_image_stream, mock_create_pdf, mock_get_additional_infos, mock_session, request_context):
        from app.views import handle_pdf_generation
        
        mock_background_image = BytesIO(b'test')
        mock_get_background_image_stream.return_value = mock_background_image
        
        fetched_appointments = [
            {'id': '1_123', 'description': 'Test 1'},
            {'id': '1_456', 'description': 'Test 2'},
            {'id': '1_789', 'description': 'Test 3'}
        ]
        mock_session.get = MagicMock(return_value=fetched_appointments)
        
        mock_get_additional_infos.return_value = {
            '1_123': 'Info 1',
            '1_456': 'Info 2'
        }
        
        mock_create_pdf.return_value = 'test.pdf'
        
        appointment_ids = ['1_123', '1_456']
        color_settings = {
            'date_color': '#c1540c',
            'background_color': '#ffffff',
            'description_color': '#4e4e4e',
            'background_alpha': 128
        }
        result = handle_pdf_generation(appointment_ids, color_settings)
        
        mock_get_background_image_stream.assert_called_once()
        
        mock_get_additional_infos.assert_called_once_with(['1_123', '1_456'])
        
        expected_appointments = [
            {'id': '1_123', 'description': 'Test 1', 'additional_info': 'Info 1'},
            {'id': '1_456', 'description': 'Test 2', 'additional_info': 'Info 2'}
        ]
        mock_create_pdf.assert_called_once_with(
            expected_appointments,
            '#c1540c',
            '#ffffff',
            '#4e4e4e',
            128,
            mock_background_image
        )
        
        assert result == 'test.pdf'
        
    @patch('app.views.convert_from_path')
    @patch('app.views.BytesIO')
    @patch('app.views.zipfile.ZipFile')
    def test_handle_jpeg_generation(self, mock_zipfile, mock_bytesio, mock_convert_from_path, request_context):
        from app.views import handle_jpeg_generation
        
        mock_image1 = MagicMock()
        mock_image2 = MagicMock()
        mock_convert_from_path.return_value = [mock_image1, mock_image2]
        
        mock_jpeg_stream1 = MagicMock()
        mock_jpeg_stream2 = MagicMock()
        mock_zip_buffer = MagicMock()
        mock_bytesio.side_effect = [mock_jpeg_stream1, mock_jpeg_stream2, mock_zip_buffer]
        
        mock_zip_file = MagicMock()
        mock_zipfile.return_value.__enter__.return_value = mock_zip_file
        
        result = handle_jpeg_generation('test.pdf')
        
        mock_convert_from_path.assert_called_once_with(os.path.join(Config.FILE_DIRECTORY, 'test.pdf'))
        
        mock_image1.save.assert_called_once_with(mock_jpeg_stream1, 'JPEG')
        mock_image2.save.assert_called_once_with(mock_jpeg_stream2, 'JPEG')
        
        assert mock_zip_file.writestr.call_count == 2
        
        assert result == mock_zip_buffer
        
    @patch('app.views.request', new_callable=MagicMock)
    def test_get_background_image_stream_with_file(self, mock_request, request_context):
        from app.views import get_background_image_stream
        
        mock_file = MagicMock()
        mock_file.filename = 'background.jpg'
        mock_file.read.return_value = b'test image data'
        mock_files = {'background_image': mock_file}
        mock_request.files = mock_files
        
        result = get_background_image_stream()
        
        assert isinstance(result, BytesIO)
        result.seek(0)
        assert result.read() == b'test image data'
        
    @patch('app.views.request', new_callable=MagicMock)
    def test_get_background_image_stream_without_file(self, mock_request, request_context):
        from app.views import get_background_image_stream
        
        mock_files = {}
        mock_request.files = mock_files
        
        result = get_background_image_stream()
        
        assert result is None
        
    def test_download_file_success(self, client):
        os.makedirs(Config.FILE_DIRECTORY, exist_ok=True)
        
        test_file_path = os.path.join(Config.FILE_DIRECTORY, 'test.pdf')
        with open(test_file_path, 'wb') as f:
            f.write(b'Test PDF content')
        
        response = client.get('/download/test.pdf')
        
        assert response.status_code == 200
        
        os.remove(test_file_path)
        
    @patch('app.views.send_from_directory')
    def test_download_file_not_found(self, mock_send_from_directory, client):
        mock_send_from_directory.side_effect = FileNotFoundError()
        
        response = client.get('/download/nonexistent.pdf')
        
        assert response.status_code == 302
        assert response.location == '/appointments'