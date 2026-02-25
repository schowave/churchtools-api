import logging
import os
import re

logger = logging.getLogger(__name__)


# Read version from APP_VERSION env var (set in Docker), or parse build script (local dev)
def get_version():
    version = os.getenv("APP_VERSION")
    if version:
        return version
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        script_path = os.path.join(base_dir, "build-and-push-docker-image.sh")
        with open(script_path, "r") as file:
            content = file.read()
            match = re.search(r"VERSION=(\d+\.\d+\.\d+)", content)
            if match:
                return match.group(1)
    except Exception as e:
        logger.error(f"Error reading version: {e}")
    return "0.0.0"


class Config:
    COOKIE_LOGIN_TOKEN = "login_token"
    VERSION = get_version()
    CHURCHTOOLS_BASE = os.getenv("CHURCHTOOLS_BASE", "<SET CHURCHTOOLS_BASE IN .ENV FILE>")
    DB_PATH = os.getenv("DB_PATH", "<SET DB_PATH IN .ENV FILE>")
    CHURCHTOOLS_BASE_URL = os.getenv("CHURCHTOOLS_BASE_URL", f"https://{CHURCHTOOLS_BASE}")
    FILE_DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saved_files")
