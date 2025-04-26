import unittest
from unittest.mock import MagicMock, patch
import os
import tempfile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import (
    Base, Appointment, ColorSetting, 
    save_additional_infos, get_additional_infos,
    save_color_settings, load_color_settings
)

class TestDatabase(unittest.TestCase):
    def setUp(self):
        # Create a temporary SQLite database for testing
        self.temp_db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db_file.close()
        
        # Create engine and session
        self.engine = create_engine(f"sqlite:///{self.temp_db_file.name}")
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # Create tables
        Base.metadata.create_all(self.engine)
    
    def tearDown(self):
        # Close session and remove temporary database
        self.session.close()
        os.unlink(self.temp_db_file.name)
    
    def test_save_and_get_additional_infos(self):
        # Test data
        appointment_info_list = [
            ("appointment1", "Info for appointment 1"),
            ("appointment2", "Info for appointment 2")
        ]
        
        # Save additional infos
        save_additional_infos(self.session, appointment_info_list)
        
        # Get additional infos
        result = get_additional_infos(self.session, ["appointment1", "appointment2", "nonexistent"])
        
        # Check results
        self.assertEqual(len(result), 2)
        self.assertEqual(result["appointment1"], "Info for appointment 1")
        self.assertEqual(result["appointment2"], "Info for appointment 2")
        self.assertNotIn("nonexistent", result)
    
    def test_update_existing_additional_info(self):
        # Create initial appointment
        self.session.add(Appointment(id="appointment3", additional_info="Initial info"))
        self.session.commit()
        
        # Update the info
        save_additional_infos(self.session, [("appointment3", "Updated info")])
        
        # Get the updated info
        result = get_additional_infos(self.session, ["appointment3"])
        
        # Check result
        self.assertEqual(result["appointment3"], "Updated info")
    
    def test_save_and_load_color_settings(self):
        # Test data
        settings = {
            'name': 'test_settings',
            'background_color': '#ffffff',
            'background_alpha': 128,
            'date_color': '#c1540c',
            'description_color': '#4e4e4e'
        }
        
        # Save color settings
        save_color_settings(self.session, settings)
        
        # Load color settings
        result = load_color_settings(self.session, 'test_settings')
        
        # Check results
        self.assertEqual(result['name'], 'test_settings')
        self.assertEqual(result['background_color'], '#ffffff')
        self.assertEqual(result['background_alpha'], 128)
        self.assertEqual(result['date_color'], '#c1540c')
        self.assertEqual(result['description_color'], '#4e4e4e')
    
    def test_load_nonexistent_color_settings(self):
        # Load nonexistent settings (should return default values)
        result = load_color_settings(self.session, 'nonexistent')
        
        # Check default values
        self.assertEqual(result['name'], 'nonexistent')
        self.assertEqual(result['background_color'], '#ffffff')
        self.assertEqual(result['background_alpha'], 128)
        self.assertEqual(result['date_color'], '#c1540c')
        self.assertEqual(result['description_color'], '#4e4e4e')
    
    def test_update_existing_color_settings(self):
        # Create initial settings
        self.session.add(ColorSetting(
            setting_name='update_test',
            background_color='#000000',
            background_alpha=100,
            date_color='#000000',
            description_color='#000000'
        ))
        self.session.commit()
        
        # Update settings
        updated_settings = {
            'name': 'update_test',
            'background_color': '#ffffff',
            'background_alpha': 200,
            'date_color': '#ff0000',
            'description_color': '#00ff00'
        }
        save_color_settings(self.session, updated_settings)
        
        # Load updated settings
        result = load_color_settings(self.session, 'update_test')
        
        # Check results
        self.assertEqual(result['background_color'], '#ffffff')
        self.assertEqual(result['background_alpha'], 200)
        self.assertEqual(result['date_color'], '#ff0000')
        self.assertEqual(result['description_color'], '#00ff00')
    
    def test_database_error_handling(self):
        # Test error handling in get_additional_infos
        with patch('app.database.print') as mock_print:
            # Create a session that raises an exception when queried
            mock_session = MagicMock()
            mock_session.query.side_effect = Exception("Database error")
            
            # Call function with mocked session
            result = get_additional_infos(mock_session, ["appointment1"])
            
            # Check that error was handled and empty dict returned
            self.assertEqual(result, {})
            mock_print.assert_called_once()
            self.assertIn("Database error", mock_print.call_args[0][0])
    
    def test_load_color_settings_error_handling(self):
        # Test error handling in load_color_settings
        with patch('app.database.print') as mock_print:
            # Create a session that raises an exception when queried
            mock_session = MagicMock()
            mock_session.query.side_effect = Exception("Database error")
            
            # Call function with mocked session
            result = load_color_settings(mock_session, "test")
            
            # Check that default settings were returned
            self.assertEqual(result['name'], 'test')
            self.assertEqual(result['background_color'], '#ffffff')
            mock_print.assert_called_once()
            self.assertIn("An error occurred", mock_print.call_args[0][0])

if __name__ == '__main__':
    unittest.main()