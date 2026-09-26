import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.crud import (
    claim_legacy_additional_infos,
    get_additional_infos,
    load_color_settings,
    save_additional_infos,
    save_color_settings,
)
from app.database import Base
from app.models import Appointment, ColorSetting
from app.schemas import ColorSettings


class TestDatabase(unittest.TestCase):
    def setUp(self):
        # Create a temporary SQLite database for testing
        self.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
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

    def test_claim_legacy_additional_infos_moves_text_to_current_id(self):
        save_additional_infos(self.session, [("1_101", "Old text"), ("1_101_1", "Second"), ("1_102", "")])

        claimed = claim_legacy_additional_infos(
            self.session,
            {
                "1_101_2026-10-04T08:00:00Z": "1_101",
                "1_101_2026-10-11T08:00:00Z": "1_101_1",
                "1_102_2026-10-05T18:00:00Z": "1_102",
            },
        )

        assert claimed == {"1_101_2026-10-04T08:00:00Z": "Old text", "1_101_2026-10-11T08:00:00Z": "Second"}
        stored = {row.id: row.additional_info for row in self.session.query(Appointment).all()}
        # Legacy rows are gone, so another date range cannot attach them to other occurrences
        assert stored == claimed

    def test_claim_legacy_additional_infos_without_legacy_rows(self):
        assert claim_legacy_additional_infos(self.session, {"1_101_2026-10-04T08:00:00Z": "1_101"}) == {}
        assert claim_legacy_additional_infos(self.session, {}) == {}

    def test_save_and_get_additional_infos(self):
        # Test data
        appointment_info_list = [("appointment1", "Info for appointment 1"), ("appointment2", "Info for appointment 2")]

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
        settings = ColorSettings(
            name="test_settings",
            background_color="#ffffff",
            background_alpha=128,
            date_color="#c1540c",
            description_color="#4e4e4e",
        )

        # Save color settings
        save_color_settings(self.session, settings)

        # Load color settings
        result = load_color_settings(self.session, "test_settings")

        # Check results
        self.assertIsInstance(result, ColorSettings)
        self.assertEqual(result.name, "test_settings")
        self.assertEqual(result.background_color, "#ffffff")
        self.assertEqual(result.background_alpha, 128)
        self.assertEqual(result.date_color, "#c1540c")
        self.assertEqual(result.description_color, "#4e4e4e")

    def test_load_nonexistent_color_settings(self):
        # Load nonexistent settings (should return default values)
        result = load_color_settings(self.session, "nonexistent")

        # Check default values
        self.assertIsInstance(result, ColorSettings)
        self.assertEqual(result.name, "nonexistent")
        self.assertEqual(result.background_color, "#d3d3d3")
        self.assertEqual(result.background_alpha, 128)
        self.assertEqual(result.date_color, "#c1540c")
        self.assertEqual(result.description_color, "#4e4e4e")

    def test_update_existing_color_settings(self):
        # Create initial settings
        self.session.add(
            ColorSetting(
                setting_name="update_test",
                background_color="#000000",
                background_alpha=100,
                date_color="#000000",
                description_color="#000000",
            )
        )
        self.session.commit()

        # Update settings
        updated_settings = ColorSettings(
            name="update_test",
            background_color="#ffffff",
            background_alpha=200,
            date_color="#ff0000",
            description_color="#00ff00",
        )
        save_color_settings(self.session, updated_settings)

        # Load updated settings
        result = load_color_settings(self.session, "update_test")

        # Check results
        self.assertEqual(result.background_color, "#ffffff")
        self.assertEqual(result.background_alpha, 200)
        self.assertEqual(result.date_color, "#ff0000")
        self.assertEqual(result.description_color, "#00ff00")

    def test_database_error_handling(self):
        # Test error handling in get_additional_infos
        with patch("app.crud.logger") as mock_logger:
            # Create a session that raises an exception when queried
            mock_session = MagicMock()
            mock_session.query.side_effect = SQLAlchemyError("Database error")

            # Call function with mocked session
            result = get_additional_infos(mock_session, ["appointment1"])

            # Check that error was handled and empty dict returned
            self.assertEqual(result, {})
            mock_logger.error.assert_called_once()
            self.assertEqual("database_error", mock_logger.error.call_args[0][0])

    def test_load_color_settings_error_handling(self):
        # Test error handling in load_color_settings
        with patch("app.crud.logger") as mock_logger:
            # Create a session that raises an exception when queried
            mock_session = MagicMock()
            mock_session.query.side_effect = SQLAlchemyError("Database error")

            # Call function with mocked session
            result = load_color_settings(mock_session, "test")

            # Check that default settings were returned
            self.assertIsInstance(result, ColorSettings)
            self.assertEqual(result.name, "test")
            self.assertEqual(result.background_color, "#d3d3d3")
            mock_logger.error.assert_called_once()
            self.assertEqual("database_error", mock_logger.error.call_args[0][0])


def test_save_additional_infos_uses_a_single_statement(tmp_path):
    from sqlalchemy import event
    from sqlalchemy.orm import sessionmaker

    from app.database import Base
    from app.models import Appointment

    engine = create_engine(f"sqlite:///{tmp_path / 'upsert.db'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(Appointment(id="a1", additional_info="old"))
    session.commit()

    statements = []
    event.listen(engine, "before_cursor_execute", lambda *args: statements.append(args[2]))
    save_additional_infos(session, [(f"a{i}", f"info {i}") for i in range(1, 11)])

    writes = [s for s in statements if s.lstrip().upper().startswith(("INSERT", "UPDATE", "SELECT"))]
    assert len(writes) == 1
    stored = get_additional_infos(session, ["a1", "a10"])
    assert stored == {"a1": "info 1", "a10": "info 10"}
    session.close()


class TestProfileCRUD(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        self.engine = create_engine(f"sqlite:///{self.temp_db.name}")
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        import app.models  # noqa: F401

        Base.metadata.create_all(self.engine)

    def tearDown(self):
        self.session.close()
        os.unlink(self.temp_db.name)

    def test_list_profiles_default_only(self):
        from app.crud import list_profiles, save_color_settings
        from app.schemas import ColorSettings

        save_color_settings(self.session, ColorSettings(name="default"))
        profiles = list_profiles(self.session)
        self.assertEqual(profiles, ["default"])

    def test_list_profiles_multiple(self):
        from app.crud import list_profiles, save_color_settings
        from app.schemas import ColorSettings

        save_color_settings(self.session, ColorSettings(name="default"))
        save_color_settings(self.session, ColorSettings(name="sunday"))
        profiles = list_profiles(self.session)
        self.assertIn("default", profiles)
        self.assertIn("sunday", profiles)

    def test_clone_profile(self):
        from app.crud import clone_profile, load_color_settings, save_color_settings
        from app.schemas import ColorSettings

        save_color_settings(self.session, ColorSettings(name="default", background_color="#ff0000"))
        clone_profile(self.session, "default", "copy")
        result = load_color_settings(self.session, "copy")
        self.assertEqual(result.background_color, "#ff0000")

    def test_delete_profile_default_raises(self):
        from app.crud import delete_profile, save_color_settings
        from app.schemas import ColorSettings

        save_color_settings(self.session, ColorSettings(name="default"))
        with self.assertRaises(ValueError):
            delete_profile(self.session, "default")

    def test_delete_profile_cascades(self):
        from app.crud import delete_profile, list_profiles, save_color_settings, save_logo
        from app.schemas import ColorSettings

        save_color_settings(self.session, ColorSettings(name="temp"))
        save_logo(self.session, "temp", b"logodata", "logo.png")
        delete_profile(self.session, "temp")
        profiles = list_profiles(self.session)
        self.assertNotIn("temp", profiles)
