import unittest
from unittest.mock import patch


class TestSettings(unittest.TestCase):
    @patch.dict("os.environ", {"CHURCHTOOLS_BASE": "my-church.church.tools"}, clear=False)
    def test_settings_loads_from_env(self):
        from app.config import Settings

        s = Settings()
        assert s.churchtools_base == "my-church.church.tools"
        assert s.churchtools_base_url == "https://my-church.church.tools"
        assert s.db_path == "churchtools.db"
        assert s.cookie_session == "session"

    @patch.dict(
        "os.environ",
        {"CHURCHTOOLS_BASE": "my-church.church.tools", "CHURCHTOOLS_BASE_URL": "http://custom.url"},
        clear=False,
    )
    def test_base_url_overridable(self):
        from app.config import Settings

        s = Settings()
        assert s.churchtools_base_url == "http://custom.url"

    @patch.dict("os.environ", {}, clear=True)
    def test_empty_churchtools_base_defaults(self):
        from app.config import Settings

        s = Settings(_env_file=None)
        assert s.churchtools_base == ""
        assert s.churchtools_base_url == ""

    @patch.dict("os.environ", {"CHURCHTOOLS_BASE": "my-church.church.tools"}, clear=False)
    def test_version_reads_from_pyproject(self):
        from app.config import Settings

        s = Settings()
        assert s.version != "0.0.0"
        assert "." in s.version

    @patch.dict("os.environ", {"CHURCHTOOLS_BASE": "test.church.tools", "TIMEZONE": "America/New_York"}, clear=False)
    def test_custom_timezone(self):
        from zoneinfo import ZoneInfo

        from app.config import Settings

        s = Settings()
        assert s.timezone == ZoneInfo("America/New_York")

    @patch.dict("os.environ", {"CHURCHTOOLS_BASE": "test.church.tools", "TIMEZONE": "Invalid/Zone"}, clear=False)
    def test_invalid_timezone_raises(self):
        from pydantic import ValidationError

        from app.config import Settings

        with self.assertRaises(ValidationError):
            Settings()


class TestAccessRestrictionSettings(unittest.TestCase):
    @patch.dict("os.environ", {"ALLOWED_GROUP_IDS": "12, 15", "ALLOWED_PERSON_IDS": ""}, clear=False)
    def test_id_lists_are_parsed(self):
        from app.config import Settings, parse_ids

        s = Settings()
        assert parse_ids(s.allowed_group_ids) == {12, 15}
        assert parse_ids(s.allowed_person_ids) == set()

    @patch.dict("os.environ", {"ALLOWED_GROUP_IDS": "Mitarbeiter"}, clear=False)
    def test_typo_fails_at_startup(self):
        from pydantic import ValidationError

        from app.config import Settings

        with self.assertRaises(ValidationError) as ctx:
            Settings()
        assert "ALLOWED_GROUP_IDS" in str(ctx.exception)
