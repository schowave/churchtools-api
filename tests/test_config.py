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
        assert s.cookie_login_token == "login_token"

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
    def test_missing_churchtools_base_raises(self):
        from app.config import Settings

        with self.assertRaises(Exception):
            Settings(_env_file=None)

    @patch.dict("os.environ", {"CHURCHTOOLS_BASE": "my-church.church.tools"}, clear=False)
    def test_version_reads_from_pyproject(self):
        from app.config import Settings

        s = Settings()
        assert s.version != "0.0.0"
        assert "." in s.version
