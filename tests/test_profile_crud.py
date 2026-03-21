import os
import tempfile
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base


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
