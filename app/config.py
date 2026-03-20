import tomllib
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _read_version() -> str:
    try:
        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        with open(pyproject, "rb") as f:
            return tomllib.load(f)["project"]["version"]
    except Exception:
        return "0.0.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    churchtools_base: str
    db_path: str = "churchtools.db"
    churchtools_base_url: str = ""
    cookie_login_token: str = "login_token"
    version: str = _read_version()
    file_directory: str = str(Path(__file__).parent.parent / "saved_files")  # temp, removed in Task 5

    @model_validator(mode="after")
    def _set_base_url(self) -> "Settings":
        if not self.churchtools_base_url:
            self.churchtools_base_url = f"https://{self.churchtools_base}"
        return self


settings = Settings()
