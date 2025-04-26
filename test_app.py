import unittest
import json
import os
from unittest.mock import patch, MagicMock
from flask import url_for
from app import create_app
from config import Config


class TestConfig(Config):
    """Test-Konfiguration, die die Produktionskonfiguration überschreibt."""
    TESTING = True
    # Verwenden einer Test-Datenbank
    DB_PATH = 'test_database.db'
    # Verwenden eines festen Secret Keys für Tests
    SECRET_KEY = 'test-secret-key'
    # Verwenden eines Test-Verzeichnisses für Dateien
    FILE_DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_files')


class TestApp(unittest.TestCase):
    """Test-Klasse für die Flask-Anwendung."""

    def setUp(self):
        """Vor jedem Test ausgeführt."""
        # Erstellen einer Test-Instanz der App
        self.app = create_app()
        self.app.config.from_object(TestConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # Sicherstellen, dass das Test-Verzeichnis existiert
        os.makedirs(TestConfig.FILE_DIRECTORY, exist_ok=True)

    def tearDown(self):
        """Nach jedem Test ausgeführt."""
        self.app_context.pop()
        # Aufräumen: Test-Datenbank löschen, wenn sie existiert
        if os.path.exists(TestConfig.DB_PATH):
            os.remove(TestConfig.DB_PATH)
        # Aufräumen: Test-Dateien löschen
        if os.path.exists(TestConfig.FILE_DIRECTORY):
            for file in os.listdir(TestConfig.FILE_DIRECTORY):
                os.remove(os.path.join(TestConfig.FILE_DIRECTORY, file))

    def test_login_page_loads(self):
        """Test, ob die Login-Seite geladen wird."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'API-Zugriff', response.data)
        self.assertIn(b'Login', response.data)

    @patch('app.views.requests.post')
    @patch('app.views.requests.get')
    def test_login_success(self, mock_get, mock_post):
        """Test für erfolgreichen Login."""
        # Mock für POST-Anfrage zum Login
        mock_post_response = MagicMock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = {
            'data': {'personId': 123}
        }
        mock_post_response.cookies = {'session': 'test-session'}
        mock_post.return_value = mock_post_response
        
        # Mock für GET-Anfrage zum Token
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {
            'data': 'test-login-token'
        }
        mock_get.return_value = mock_get_response
        
        # Login-Anfrage senden
        response = self.client.post('/', data={
            'username': 'testuser',
            'password': 'testpassword'
        }, follow_redirects=True)
        
        # Überprüfen, ob zur Übersichtsseite weitergeleitet wurde
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Termin', response.data)
        
        # Überprüfen, ob die richtigen API-Aufrufe gemacht wurden
        mock_post.assert_called_once_with(
            f'{TestConfig.CHURCHTOOLS_BASE_URL}/api/login',
            json={"password": "testpassword", "rememberMe": True, "username": "testuser"}
        )
        mock_get.assert_called_once_with(
            f'{TestConfig.CHURCHTOOLS_BASE_URL}/api/persons/123/logintoken',
            cookies=mock_post_response.cookies
        )

    @patch('app.views.requests.post')
    def test_login_failure(self, mock_post):
        """Test für fehlgeschlagenen Login."""
        # Mock für fehlgeschlagene POST-Anfrage
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response
        
        # Login-Anfrage senden
        response = self.client.post('/', data={
            'username': 'wronguser',
            'password': 'wrongpassword'
        }, follow_redirects=True)
        
        # Überprüfen, ob auf der Login-Seite geblieben wird
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Login', response.data)
        self.assertIn(b'Invalid username or password', response.data)

    @patch('app.views.make_response')
    def test_logout(self, mock_make_response):
        """Test für Logout-Funktionalität."""
        # Mock für make_response
        mock_response = MagicMock()
        mock_response.set_cookie = MagicMock()
        mock_make_response.return_value = mock_response
        
        # Zuerst ein Cookie setzen, um einen eingeloggten Zustand zu simulieren
        with self.client as c:
            with c.session_transaction() as session:
                session['login_token'] = 'test-login-token'
            
            # Logout-Anfrage senden
            response = c.post('/logout')
            
            # Überprüfen, ob set_cookie aufgerufen wurde, um das Cookie zu löschen
            mock_response.set_cookie.assert_called_with('login_token', '', expires=0)
        
        # Überprüfen, ob man zur Login-Seite weitergeleitet wird, wenn man versucht,
        # auf eine geschützte Route zuzugreifen
        response = self.client.get('/overview', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Login', response.data)

    def test_protected_routes_redirect_to_login(self):
        """Test, ob geschützte Routen zur Login-Seite umleiten, wenn nicht eingeloggt."""
        # Übersichtsseite ohne Login aufrufen
        response = self.client.get('/overview', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Login', response.data)
        
        # Terminseite ohne Login aufrufen
        response = self.client.get('/appointments', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Login', response.data)

    @patch('app.views.get_login_token')
    @patch('app.utils.get_login_token')
    @patch('app.utils.fetch_calendars')
    @patch('app.utils.requests.get')
    def test_appointments_page_with_login(self, mock_requests_get, mock_fetch_calendars,
                                         mock_utils_get_login_token, mock_views_get_login_token):
        """Test, ob die Terminseite mit Login geladen wird."""
        # Mock für Login-Token
        mock_utils_get_login_token.return_value = 'test-login-token'
        mock_views_get_login_token.return_value = 'test-login-token'
        
        # Mock für requests.get
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            'data': [
                {'id': 1, 'name': 'Kalender 1', 'isPublic': True},
                {'id': 2, 'name': 'Kalender 2', 'isPublic': True}
            ]
        }
        mock_requests_get.return_value = mock_response
        
        # Mock für Kalender
        mock_fetch_calendars.return_value = [
            {'id': 1, 'name': 'Kalender 1', 'isPublic': True},
            {'id': 2, 'name': 'Kalender 2', 'isPublic': True}
        ]
        
        # Cookie setzen für die Authentifizierung
        with self.client as c:
            with c.session_transaction() as session:
                session['login_token'] = 'test-login-token'
            
            # Terminseite mit Login aufrufen
            response = c.get('/appointments')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Termin', response.data)

    @patch('app.views.get_login_token')
    @patch('app.utils.get_login_token')
    @patch('app.utils.fetch_calendars')
    @patch('app.views.fetch_appointments')
    @patch('app.views.get_additional_infos')
    @patch('app.utils.requests.get')
    def test_fetch_appointments(self, mock_requests_get, mock_get_additional_infos,
                               mock_fetch_appointments, mock_fetch_calendars,
                               mock_utils_get_login_token, mock_views_get_login_token):
        """Test für das Abrufen von Terminen."""
        # Mocks einrichten
        mock_utils_get_login_token.return_value = 'test-login-token'
        mock_views_get_login_token.return_value = 'test-login-token'
        
        # Mock für requests.get
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            'data': [
                {'id': 1, 'name': 'Kalender 1', 'isPublic': True}
            ]
        }
        mock_requests_get.return_value = mock_response
        
        mock_fetch_calendars.return_value = [
            {'id': 1, 'name': 'Kalender 1', 'isPublic': True}
        ]
        
        # Mock für Termine
        mock_appointment = {
            'base': {
                'id': '1_123',
                'caption': 'Test Termin',
                'information': 'Test Info',
                'address': {'meetingAt': 'Test Ort'}
            },
            'calculated': {
                'startDate': '2023-01-01T10:00:00Z',
                'endDate': '2023-01-01T11:00:00Z'
            }
        }
        mock_fetch_appointments.return_value = [mock_appointment]
        
        # Mock für zusätzliche Infos
        mock_get_additional_infos.return_value = {'1_123': 'Zusätzliche Info'}
        
        # Cookie setzen und Anfrage zum Abrufen von Terminen
        with self.client as c:
            with c.session_transaction() as session:
                session['selected_calendar_ids'] = ['1']
                session['login_token'] = 'test-login-token'
            
            response = c.post('/appointments', data={
                'start_date': '2023-01-01',
                'end_date': '2023-01-31',
                'calendar_ids': ['1'],
                'fetch_appointments': 'true'
            })
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Test Termin', response.data)

    @patch('app.views.get_login_token')
    @patch('app.utils.get_login_token')
    @patch('app.views.fetch_calendars')
    @patch('app.views.fetch_appointments')
    @patch('app.views.get_additional_infos')
    @patch('app.views.create_pdf')
    @patch('app.utils.requests.get')
    @patch('app.views.send_from_directory')
    def test_pdf_generation(self, mock_send_from_directory, mock_requests_get,
                           mock_create_pdf, mock_get_additional_infos,
                           mock_fetch_appointments, mock_fetch_calendars,
                           mock_utils_get_login_token, mock_views_get_login_token):
        """Test für die PDF-Generierung."""
        # Mocks einrichten
        mock_utils_get_login_token.return_value = 'test-login-token'
        mock_views_get_login_token.return_value = 'test-login-token'
        
        # Mock für requests.get
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            'data': [
                {'id': 1, 'name': 'Kalender 1', 'isPublic': True}
            ]
        }
        mock_requests_get.return_value = mock_response
        
        # Mock für send_from_directory
        mock_send_from_directory.return_value = MagicMock()
        
        mock_fetch_calendars.return_value = [
            {'id': 1, 'name': 'Kalender 1', 'isPublic': True}
        ]
        
        # Mock für Termine
        mock_appointment = {
            'base': {
                'id': '1_123',
                'caption': 'Test Termin',
                'information': 'Test Info',
                'address': {'meetingAt': 'Test Ort'}
            },
            'calculated': {
                'startDate': '2023-01-01T10:00:00Z',
                'endDate': '2023-01-01T11:00:00Z'
            }
        }
        mock_fetch_appointments.return_value = [mock_appointment]
        
        # Mock für zusätzliche Infos
        mock_get_additional_infos.return_value = {'1_123': 'Zusatzinfo'}
        
        # Mock für PDF-Generierung
        mock_create_pdf.return_value = 'test_file.pdf'
        
        # Cookie setzen und Sitzungsdaten vorbereiten
        with self.client as c:
            with c.session_transaction() as session:
                session['fetched_appointments'] = [{
                    'id': '1_123',
                    'description': 'Test Termin',
                    'startDate': '2023-01-01T10:00:00Z',
                    'endDate': '2023-01-01T11:00:00Z',
                    'address': {'meetingAt': 'Test Ort'},
                    'information': 'Test Info',
                    'startDateView': '01.01.2023',
                    'startTimeView': '10:00',
                    'endTimeView': '11:00',
                    'additional_info': 'Zusatzinfo'
                }]
                session['login_token'] = 'test-login-token'
            
            # Anfrage zur PDF-Generierung
            response = c.post('/appointments', data={
                'start_date': '2023-01-01',
                'end_date': '2023-01-31',
                'calendar_ids': ['1'],
                'appointment_id': ['1_123'],
                'additional_info_1_123': 'Zusatzinfo',
                'date_color': '#c1540c',
                'description_color': '#4e4e4e',
                'background_color': '#ffffff',
                'alpha': '128',
                'generate_pdf': 'true'
            }, follow_redirects=True)
        
        # Überprüfen, ob die PDF-Generierung aufgerufen wurde
        mock_create_pdf.assert_called_once()
        
        # Überprüfen, ob zur Download-Seite weitergeleitet wurde
        self.assertEqual(response.status_code, 200)

    @patch('app.views.get_login_token')
    @patch('app.utils.get_login_token')
    @patch('app.views.fetch_calendars')
    @patch('app.views.fetch_appointments')
    @patch('app.views.get_additional_infos')
    @patch('app.views.create_pdf')
    @patch('app.views.convert_from_path')
    @patch('app.utils.requests.get')
    @patch('app.views.send_file')
    def test_jpeg_generation(self, mock_send_file, mock_requests_get,
                            mock_convert_from_path, mock_create_pdf,
                            mock_get_additional_infos, mock_fetch_appointments,
                            mock_fetch_calendars, mock_utils_get_login_token, mock_views_get_login_token):
        """Test für die JPEG-Generierung."""
        # Mocks einrichten
        mock_utils_get_login_token.return_value = 'test-login-token'
        mock_views_get_login_token.return_value = 'test-login-token'
        
        # Mock für requests.get
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            'data': [
                {'id': 1, 'name': 'Kalender 1', 'isPublic': True}
            ]
        }
        mock_requests_get.return_value = mock_response
        
        # Mock für send_file
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.mimetype = 'application/zip'
        mock_send_file.return_value = mock_response
        
        mock_fetch_calendars.return_value = [
            {'id': 1, 'name': 'Kalender 1', 'isPublic': True}
        ]
        
        # Mock für Termine
        mock_appointment = {
            'base': {
                'id': '1_123',
                'caption': 'Test Termin',
                'information': 'Test Info',
                'address': {'meetingAt': 'Test Ort'}
            },
            'calculated': {
                'startDate': '2023-01-01T10:00:00Z',
                'endDate': '2023-01-01T11:00:00Z'
            }
        }
        mock_fetch_appointments.return_value = [mock_appointment]
        
        # Mock für zusätzliche Infos
        mock_get_additional_infos.return_value = {'1_123': 'Zusatzinfo'}
        
        # Mock für PDF-Generierung
        mock_create_pdf.return_value = 'test_file.pdf'
        
        # Mock für PDF-zu-Bild-Konvertierung
        mock_image = MagicMock()
        mock_image.save = MagicMock()
        mock_convert_from_path.return_value = [mock_image]
        
        # Cookie setzen und Sitzungsdaten vorbereiten
        with self.client as c:
            with c.session_transaction() as session:
                session['fetched_appointments'] = [{
                    'id': '1_123',
                    'description': 'Test Termin',
                    'startDate': '2023-01-01T10:00:00Z',
                    'endDate': '2023-01-01T11:00:00Z',
                    'address': {'meetingAt': 'Test Ort'},
                    'information': 'Test Info',
                    'startDateView': '01.01.2023',
                    'startTimeView': '10:00',
                    'endTimeView': '11:00',
                    'additional_info': 'Zusatzinfo'
                }]
                session['login_token'] = 'test-login-token'
            
            # Anfrage zur JPEG-Generierung
            response = c.post('/appointments', data={
                'start_date': '2023-01-01',
                'end_date': '2023-01-31',
                'calendar_ids': ['1'],
                'appointment_id': ['1_123'],
                'additional_info_1_123': 'Zusatzinfo',
                'date_color': '#c1540c',
                'description_color': '#4e4e4e',
                'background_color': '#ffffff',
                'alpha': '128',
                'generate_jpeg': 'true'
            }, follow_redirects=True)
        
        # Überprüfen, ob die PDF-Generierung aufgerufen wurde
        mock_create_pdf.assert_called_once()
        
        # Überprüfen, ob die PDF-zu-Bild-Konvertierung aufgerufen wurde
        mock_convert_from_path.assert_called_once()
        
        # Überprüfen, ob die Bild-Speicherung aufgerufen wurde
        mock_image.save.assert_called_once()
        
        # Da wir den send_file-Aufruf mocken, überprüfen wir nur, ob er aufgerufen wurde
        mock_send_file.assert_called_once()


class TestUtils(unittest.TestCase):
    """Test-Klasse für die Hilfsfunktionen."""

    def setUp(self):
        """Vor jedem Test ausgeführt."""
        self.app = create_app()
        self.app.config.from_object(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # Sicherstellen, dass das Test-Verzeichnis existiert
        os.makedirs(TestConfig.FILE_DIRECTORY, exist_ok=True)

    def tearDown(self):
        """Nach jedem Test ausgeführt."""
        self.app_context.pop()
        # Aufräumen: Test-Datenbank löschen, wenn sie existiert
        if os.path.exists(TestConfig.DB_PATH):
            os.remove(TestConfig.DB_PATH)
        # Aufräumen: Test-Dateien löschen
        if os.path.exists(TestConfig.FILE_DIRECTORY):
            for file in os.listdir(TestConfig.FILE_DIRECTORY):
                os.remove(os.path.join(TestConfig.FILE_DIRECTORY, file))

    def test_parse_iso_datetime(self):
        """Test für die parse_iso_datetime-Funktion."""
        from app.utils import parse_iso_datetime
        
        # Test mit UTC-Zeit (Z am Ende)
        dt = parse_iso_datetime('2023-01-01T10:00:00Z')
        self.assertEqual(dt.year, 2023)
        self.assertEqual(dt.month, 1)
        self.assertEqual(dt.day, 1)
        # Die Stunde kann je nach Zeitzone variieren, daher nicht testen
        
        # Test ohne Z am Ende
        dt = parse_iso_datetime('2023-01-01T10:00:00')
        self.assertEqual(dt.year, 2023)
        self.assertEqual(dt.month, 1)
        self.assertEqual(dt.day, 1)

    def test_normalize_newlines(self):
        """Test für die normalize_newlines-Funktion."""
        from app.utils import normalize_newlines
        
        # Test mit Windows-Zeilenumbrüchen
        text = "Zeile 1\r\nZeile 2\r\nZeile 3"
        normalized = normalize_newlines(text)
        self.assertEqual(normalized, "Zeile 1\nZeile 2\nZeile 3")
        
        # Test mit Unix-Zeilenumbrüchen
        text = "Zeile 1\nZeile 2\nZeile 3"
        normalized = normalize_newlines(text)
        self.assertEqual(normalized, "Zeile 1\nZeile 2\nZeile 3")
        
        # Test mit gemischten Zeilenumbrüchen
        text = "Zeile 1\r\nZeile 2\nZeile 3"
        normalized = normalize_newlines(text)
        self.assertEqual(normalized, "Zeile 1\nZeile 2\nZeile 3")

    def test_appointment_to_dict(self):
        """Test für die appointment_to_dict-Funktion."""
        from app.utils import appointment_to_dict
        
        # Test-Appointment erstellen
        appointment = {
            'base': {
                'id': '1_123',
                'caption': 'Test Termin',
                'information': 'Test Info',
                'address': {'meetingAt': 'Test Ort'}
            },
            'calculated': {
                'startDate': '2023-01-01T10:00:00Z',
                'endDate': '2023-01-01T11:00:00Z'
            }
        }
        
        # Appointment in Dict umwandeln
        result = appointment_to_dict(appointment)
        
        # Überprüfen, ob alle erwarteten Felder vorhanden sind
        self.assertEqual(result['id'], '1_123')
        self.assertEqual(result['description'], 'Test Termin')
        self.assertEqual(result['startDate'], '2023-01-01T10:00:00Z')
        self.assertEqual(result['endDate'], '2023-01-01T11:00:00Z')
        self.assertEqual(result['information'], 'Test Info')
        self.assertEqual(result['meetingAt'], 'Test Ort')
        self.assertEqual(result['startDateView'], '01.01.2023')
        self.assertTrue('startTimeView' in result)
        self.assertTrue('endTimeView' in result)
        self.assertEqual(result['additional_info'], "")

    @patch('app.utils.requests.get')
    def test_fetch_calendars(self, mock_get):
        """Test für die fetch_calendars-Funktion."""
        from app.utils import fetch_calendars
        
        # Mock für requests.get
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            'data': [
                {'id': 1, 'name': 'Kalender 1', 'isPublic': True},
                {'id': 2, 'name': 'Kalender 2', 'isPublic': True},
                {'id': 3, 'name': 'Kalender 3', 'isPublic': False}
            ]
        }
        mock_get.return_value = mock_response
        
        # Kalender abrufen
        calendars = fetch_calendars('test-login-token')
        
        # Überprüfen, ob nur öffentliche Kalender zurückgegeben werden
        self.assertEqual(len(calendars), 2)
        self.assertEqual(calendars[0]['id'], 1)
        self.assertEqual(calendars[1]['id'], 2)
        
        # Überprüfen, ob der API-Aufruf korrekt gemacht wurde
        mock_get.assert_called_once_with(
            f'{TestConfig.CHURCHTOOLS_BASE_URL}/api/calendars',
            headers={'Authorization': 'Login test-login-token'}
        )

    @patch('app.utils.requests.get')
    def test_fetch_appointments(self, mock_get):
        """Test für die fetch_appointments-Funktion."""
        from app.utils import fetch_appointments
        
        # Mock für requests.get
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            'data': [
                {
                    'base': {
                        'id': '123',
                        'caption': 'Test Termin 1',
                        'information': 'Test Info 1',
                        'address': {'meetingAt': 'Test Ort 1'}
                    },
                    'calculated': {
                        'startDate': '2023-01-01T10:00:00Z',
                        'endDate': '2023-01-01T11:00:00Z'
                    }
                },
                {
                    'base': {
                        'id': '123',  # Gleiche ID wie oben, um Duplikate zu testen
                        'caption': 'Test Termin 2',
                        'information': 'Test Info 2',
                        'address': {'meetingAt': 'Test Ort 2'}
                    },
                    'calculated': {
                        'startDate': '2023-01-02T10:00:00Z',
                        'endDate': '2023-01-02T11:00:00Z'
                    }
                }
            ]
        }
        mock_get.return_value = mock_response
        
        # Termine abrufen
        appointments = fetch_appointments('test-login-token', '2023-01-01', '2023-01-31', [1])
        
        # Überprüfen, ob die Termine korrekt zurückgegeben werden
        self.assertEqual(len(appointments), 2)
        self.assertEqual(appointments[0]['base']['id'], '1_123')
        self.assertEqual(appointments[1]['base']['id'], '1_123_1')
        
        # Überprüfen, ob der API-Aufruf korrekt gemacht wurde
        mock_get.assert_called_once_with(
            f'{TestConfig.CHURCHTOOLS_BASE_URL}/api/calendars/1/appointments',
            headers={'Authorization': 'Login test-login-token'},
            params={'from': '2023-01-01', 'to': '2023-01-31'}
        )

    def test_save_and_get_additional_infos(self):
        """Test für die save_additional_infos- und get_additional_infos-Funktionen."""
        from app.utils import save_additional_infos, get_additional_infos
        from app import create_schema
        
        # Schema erstellen
        create_schema()
        
        # Zusätzliche Infos speichern
        appointment_info_list = [
            ('1_123', 'Zusatzinfo 1'),
            ('1_456', 'Zusatzinfo 2')
        ]
        save_additional_infos(appointment_info_list)
        
        # Zusätzliche Infos abrufen
        infos = get_additional_infos(['1_123', '1_456', '1_789'])
        
        # Überprüfen, ob die Infos korrekt zurückgegeben werden
        self.assertEqual(len(infos), 2)
        self.assertEqual(infos['1_123'], 'Zusatzinfo 1')
        self.assertEqual(infos['1_456'], 'Zusatzinfo 2')
        self.assertNotIn('1_789', infos)

    def test_save_and_load_color_settings(self):
        """Test für die save_color_settings- und load_color_settings-Funktionen."""
        from app.utils import save_color_settings, load_color_settings
        from app import create_schema
        
        # Schema erstellen
        create_schema()
        
        # Farbeinstellungen speichern
        settings = {
            'name': 'test',
            'background_color': '#ffffff',
            'background_alpha': 128,
            'date_color': '#c1540c',
            'description_color': '#4e4e4e'
        }
        save_color_settings(settings)
        
        # Farbeinstellungen laden
        loaded_settings = load_color_settings('test')
        
        # Überprüfen, ob die Einstellungen korrekt zurückgegeben werden
        self.assertEqual(loaded_settings['name'], 'test')
        self.assertEqual(loaded_settings['background_color'], '#ffffff')
        self.assertEqual(loaded_settings['background_alpha'], 128)
        self.assertEqual(loaded_settings['date_color'], '#c1540c')
        self.assertEqual(loaded_settings['description_color'], '#4e4e4e')
        
        # Nicht existierende Einstellungen laden
        default_settings = load_color_settings('nicht_existent')
        
        # Überprüfen, ob die Standardeinstellungen zurückgegeben werden
        self.assertEqual(default_settings['name'], 'nicht_existent')
        self.assertEqual(default_settings['background_color'], '#ffffff')
        self.assertEqual(default_settings['background_alpha'], 128)
        self.assertEqual(default_settings['date_color'], '#c1540c')
        self.assertEqual(default_settings['description_color'], '#4e4e4e')


class TestPdfGenerator(unittest.TestCase):
    """Test-Klasse für die PDF-Generator-Funktionen."""

    def setUp(self):
        """Vor jedem Test ausgeführt."""
        self.app = create_app()
        self.app.config.from_object(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # Sicherstellen, dass das Test-Verzeichnis existiert
        os.makedirs(TestConfig.FILE_DIRECTORY, exist_ok=True)

    def tearDown(self):
        """Nach jedem Test ausgeführt."""
        self.app_context.pop()
        # Aufräumen: Test-Dateien löschen
        if os.path.exists(TestConfig.FILE_DIRECTORY):
            for file in os.listdir(TestConfig.FILE_DIRECTORY):
                os.remove(os.path.join(TestConfig.FILE_DIRECTORY, file))

    @patch('app.pdf_generator.canvas.Canvas')
    @patch('app.pdf_generator.ImageReader')
    @patch('app.pdf_generator.pdfmetrics')
    def test_create_pdf_without_background(self, mock_pdfmetrics, mock_image_reader, mock_canvas):
        """Test für die create_pdf-Funktion ohne Hintergrundbild."""
        from app.pdf_generator import create_pdf
        
        # Mock für Canvas
        mock_canvas_instance = MagicMock()
        mock_canvas.return_value = mock_canvas_instance
        
        # Mock für pdfmetrics
        mock_pdfmetrics.getRegisteredFontNames.return_value = ['Bahnschrift']
        mock_pdfmetrics.stringWidth.return_value = 100  # Beliebige Breite für den Test
        
        # Test-Appointments erstellen
        appointments = [
            {
                'id': '1_123',
                'description': 'Test Termin 1',
                'startDate': '2023-01-01T10:00:00Z',
                'endDate': '2023-01-01T11:00:00Z',
                'meetingAt': 'Test Ort 1',  # Direkter Schlüssel statt in address
                'information': 'Test Info 1',
                'startDateView': '01.01.2023',
                'startTimeView': '10:00',
                'endTimeView': '11:00',
                'additional_info': 'Zusatzinfo 1'
            },
            {
                'id': '1_456',
                'description': 'Test Termin 2',
                'startDate': '2023-01-02T10:00:00Z',
                'endDate': '2023-01-02T11:00:00Z',
                'meetingAt': 'Test Ort 2',  # Direkter Schlüssel statt in address
                'information': 'Test Info 2',
                'startDateView': '02.01.2023',
                'startTimeView': '10:00',
                'endTimeView': '11:00',
                'additional_info': 'Zusatzinfo 2'
            }
        ]
        
        # PDF erstellen
        filename = create_pdf(appointments, '#c1540c', '#ffffff', '#4e4e4e', 128, None)
        
        # Überprüfen, ob die Datei erstellt wurde
        self.assertTrue(filename.endswith('.pdf'))
        
        # Überprüfen, ob Canvas-Methoden aufgerufen wurden
        mock_canvas_instance.setFont.assert_called()
        mock_canvas_instance.drawString.assert_called()
        mock_canvas_instance.save.assert_called_once()
        
        # Wir können nicht überprüfen, ob ImageReader nicht aufgerufen wurde,
        # da es auch in der draw_transparent_rectangle-Funktion verwendet wird

    @patch('app.pdf_generator.canvas.Canvas')
    @patch('app.pdf_generator.ImageReader')
    @patch('app.pdf_generator.pdfmetrics')
    def test_create_pdf_with_background(self, mock_pdfmetrics, mock_image_reader, mock_canvas):
        """Test für die create_pdf-Funktion mit Hintergrundbild."""
        from app.pdf_generator import create_pdf
        from io import BytesIO
        
        # Mock für Canvas
        mock_canvas_instance = MagicMock()
        mock_canvas.return_value = mock_canvas_instance
        
        # Mock für ImageReader
        mock_image_reader_instance = MagicMock()
        mock_image_reader_instance.getSize.return_value = (800, 600)  # Beispielgröße
        mock_image_reader.return_value = mock_image_reader_instance
        
        # Mock für pdfmetrics
        mock_pdfmetrics.getRegisteredFontNames.return_value = ['Bahnschrift']
        mock_pdfmetrics.stringWidth.return_value = 100  # Beliebige Breite für den Test
        
        # Test-Appointments erstellen
        appointments = [
            {
                'id': '1_123',
                'description': 'Test Termin 1',
                'startDate': '2023-01-01T10:00:00Z',
                'endDate': '2023-01-01T11:00:00Z',
                'meetingAt': 'Test Ort 1',  # Direkter Schlüssel statt in address
                'information': 'Test Info 1',
                'startDateView': '01.01.2023',
                'startTimeView': '10:00',
                'endTimeView': '11:00',
                'additional_info': 'Zusatzinfo 1'
            }
        ]
        
        # Hintergrundbild erstellen
        background_image_stream = BytesIO(b'test')
        
        # PDF erstellen
        filename = create_pdf(appointments, '#c1540c', '#ffffff', '#4e4e4e', 128, background_image_stream)
        
        # Überprüfen, ob die Datei erstellt wurde
        self.assertTrue(filename.endswith('.pdf'))
        
        # Überprüfen, ob Canvas-Methoden aufgerufen wurden
        mock_canvas_instance.setFont.assert_called()
        mock_canvas_instance.drawString.assert_called()
        mock_canvas_instance.save.assert_called_once()
        
        # Überprüfen, ob drawImage aufgerufen wurde (für das Hintergrundbild)
        mock_canvas_instance.drawImage.assert_called()


if __name__ == '__main__':
    unittest.main()