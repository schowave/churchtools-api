import tomllib
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _read_version() -> str:
    try:
        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        with open(pyproject, "rb") as f:
            return tomllib.load(f)["project"]["version"]
    except Exception:
        return "0.0.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        arbitrary_types_allowed=True,
    )

    churchtools_base: str
    db_path: str = "churchtools.db"
    churchtools_base_url: str = ""
    cookie_login_token: str = "login_token"
    version: str = _read_version()
    file_directory: str = str(Path(__file__).parent.parent / "saved_files")  # temp, removed in Task 5
    timezone_name: str = Field(default="Europe/Berlin", validation_alias="TIMEZONE")
    timezone: Optional[ZoneInfo] = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def _set_computed_defaults(self) -> "Settings":
        if not self.churchtools_base_url:
            self.churchtools_base_url = f"https://{self.churchtools_base}"
        try:
            object.__setattr__(self, "timezone", ZoneInfo(self.timezone_name))
        except (ZoneInfoNotFoundError, KeyError) as e:
            raise ValueError(f"Invalid timezone: {self.timezone_name}") from e
        return self


settings = Settings()
