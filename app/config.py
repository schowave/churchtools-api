import logging
import os
import tomllib

logger = logging.getLogger(__name__)


def get_version():
    """Read version from pyproject.toml (single source of truth)."""
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(base_dir, "pyproject.toml"), "rb") as f:
            return tomllib.load(f)["project"]["version"]
    except Exception as e:
        logger.error(f"Error reading version: {e}")
    return "0.0.0"


class Config:
    COOKIE_LOGIN_TOKEN = "login_token"
    VERSION = get_version()
    CHURCHTOOLS_BASE = os.getenv("CHURCHTOOLS_BASE", "<SET CHURCHTOOLS_BASE IN .ENV FILE>")
    DB_PATH = os.getenv("DB_PATH", "<SET DB_PATH IN .ENV FILE>")
    CHURCHTOOLS_BASE_URL = os.getenv("CHURCHTOOLS_BASE_URL", f"https://{CHURCHTOOLS_BASE}")
    FILE_DIRECTORY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "saved_files")

    @classmethod
    def validate(cls):
        missing = []
        if cls.CHURCHTOOLS_BASE.startswith("<SET"):
            missing.append("CHURCHTOOLS_BASE")
        if cls.DB_PATH.startswith("<SET"):
            missing.append("DB_PATH")
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
