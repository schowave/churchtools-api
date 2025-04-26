import unittest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock
import io
from datetime import datetime
from PyPDF2 import PdfReader
from app.services.pdf_generator import create_pdf
from app.config import Config

class TestPdfIntegration(unittest.TestCase):
    def setUp(self):
        # Erstelle ein temporäres Verzeichnis für die Tests
        self.test_dir = tempfile.mkdtemp()
        self.config_patch = patch('app.services.pdf_generator.Config', 
                                 FILE_DIRECTORY=self.test_dir)
        self.config_patch.start()
    
    def tearDown(self):
        # Entferne das temporäre Verzeichnis nach den Tests
        self.config_patch.stop()
        shutil.rmtree(self.test_dir)
    
    def test_pdf_creation_and_content(self):
        """
        Integrationstest für die PDF-Erstellung.
        Erstellt eine tatsächliche PDF-Datei und überprüft ihren Inhalt.
        """
        # Testdaten für Termine
        appointments = [
            {
                'id': '1_101',
                'description': 'Gottesdienst',
                'startDate': '2023-01-15T10:00:00Z',
                'endDate': '2023-01-15T12:00:00Z',
                'information': 'Predigt: Pastor Schmidt',
                'meetingAt': 'Hauptkirche',
                'startDateView': '15.01.2023',
                'startTimeView': '11:00',
                'endTimeView': '13:00',
                'additional_info': 'Kollekte für Jugendarbeit'
            },
            {
                'id': '1_102',
                'description': 'Bibelkreis',
                'startDate': '2023-01-16T18:00:00Z',
                'endDate': '2023-01-16T20:00:00Z',
                'information': 'Thema: Psalmen',
                'meetingAt': 'Gemeindehaus',
                'startDateView': '16.01.2023',
                'startTimeView': '19:00',
                'endTimeView': '21:00',
                'additional_info': 'Bitte Bibel mitbringen'
            }
        ]
        
        # Mock für datetime.now, um ein konsistentes Dateidatum zu haben
        with patch('app.services.pdf_generator.datetime') as mock_datetime:
            mock_now = MagicMock()
            mock_now.strftime.return_value = '2023-01-15'
            mock_datetime.now.return_value = mock_now
            
            # Erstelle die PDF
            filename = create_pdf(
                appointments,
                '#c1540c',  # date_color
                '#ffffff',  # background_color
                '#4e4e4e',  # description_color
                128,        # alpha
                None        # image_stream
            )
            
            # Überprüfe, ob die Datei erstellt wurde
            pdf_path = os.path.join(self.test_dir, filename)
            self.assertTrue(os.path.exists(pdf_path), f"PDF-Datei wurde nicht erstellt: {pdf_path}")
            
            # Öffne die PDF und überprüfe ihren Inhalt
            with open(pdf_path, 'rb') as f:
                pdf = PdfReader(f)
                
                # Überprüfe die Anzahl der Seiten
                self.assertGreaterEqual(len(pdf.pages), 1, "PDF sollte mindestens eine Seite haben")
                
                # Extrahiere den Text aus der ersten Seite
                text = pdf.pages[0].extract_text()
                
                # Überprüfe, ob die wichtigsten Informationen enthalten sind
                self.assertIn("Gottesdienst", text, "Beschreibung des ersten Termins fehlt")
                self.assertIn("Bibelkreis", text, "Beschreibung des zweiten Termins fehlt")
                self.assertIn("15.01.2023", text, "Datum des ersten Termins fehlt")
                self.assertIn("16.01.2023", text, "Datum des zweiten Termins fehlt")
                self.assertIn("11:00", text, "Startzeit des ersten Termins fehlt")
                self.assertIn("19:00", text, "Startzeit des zweiten Termins fehlt")
                self.assertIn("Hauptkirche", text, "Ort des ersten Termins fehlt")
                self.assertIn("Gemeindehaus", text, "Ort des zweiten Termins fehlt")
    
    def test_pdf_creation_with_background_image(self):
        """
        Integrationstest für die PDF-Erstellung mit Hintergrundbild.
        """
        # Erstelle ein einfaches Testbild
        from PIL import Image
        img = Image.new('RGB', (1200, 675), color=(73, 109, 137))
        img_stream = io.BytesIO()
        img.save(img_stream, format='PNG')
        img_stream.seek(0)
        
        # Testdaten für Termine
        appointments = [
            {
                'id': '1_101',
                'description': 'Jugendgottesdienst',
                'startDate': '2023-01-15T17:00:00Z',
                'endDate': '2023-01-15T19:00:00Z',
                'information': 'Mit Jugendband',
                'meetingAt': 'Jugendkirche',
                'startDateView': '15.01.2023',
                'startTimeView': '18:00',
                'endTimeView': '20:00',
                'additional_info': 'Anschließend gemeinsames Essen'
            }
        ]
        
        # Mock für datetime.now, um ein konsistentes Dateidatum zu haben
        with patch('app.services.pdf_generator.datetime') as mock_datetime:
            mock_now = MagicMock()
            mock_now.strftime.return_value = '2023-01-15'
            mock_datetime.now.return_value = mock_now
            
            # Erstelle die PDF mit Hintergrundbild
            filename = create_pdf(
                appointments,
                '#c1540c',  # date_color
                '#ffffff',  # background_color
                '#4e4e4e',  # description_color
                128,        # alpha
                img_stream  # image_stream
            )
            
            # Überprüfe, ob die Datei erstellt wurde
            pdf_path = os.path.join(self.test_dir, filename)
            self.assertTrue(os.path.exists(pdf_path), f"PDF-Datei wurde nicht erstellt: {pdf_path}")
            
            # Überprüfe die Dateigröße - mit Bild sollte die Datei größer sein
            file_size = os.path.getsize(pdf_path)
            self.assertGreater(file_size, 5000, "PDF-Datei ist zu klein, Bild wurde möglicherweise nicht eingefügt")

if __name__ == '__main__':
    unittest.main()