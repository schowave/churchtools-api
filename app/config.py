import tomllib
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Package directory; templates, static files and fonts are resolved from here, not from the CWD.
APP_DIR = Path(__file__).resolve().parent


def _read_version() -> str:
    try:
        pyproject = APP_DIR.parent / "pyproject.toml"
        with open(pyproject, "rb") as f:
            return tomllib.load(f)["project"]["version"]
    except Exception:
        return "0.0.0"


def parse_ids(value: str) -> set[int]:
    """Comma-separated ids ("7, 42") as a set; blanks are ignored, anything else raises ValueError."""
    return {int(part) for part in value.replace(";", ",").split(",") if part.strip()}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        arbitrary_types_allowed=True,
    )

    churchtools_base: str = ""
    db_path: str = "churchtools.db"
    churchtools_base_url: str = ""
    cookie_session: str = "session"
    version: str = _read_version()
    timezone_name: str = Field(default="Europe/Berlin", validation_alias="TIMEZONE")
    log_format: str = "console"  # "console" or "json"
    # Optional access restriction, comma-separated ChurchTools ids. Both empty: every ChurchTools login may use
    # the app. Otherwise a person needs to be listed or be an active member of one of the groups.
    allowed_person_ids: str = ""
    allowed_group_ids: str = ""
    timezone: ZoneInfo | None = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def _set_computed_defaults(self) -> Settings:
        if not self.churchtools_base_url and self.churchtools_base:
            self.churchtools_base_url = f"https://{self.churchtools_base}"
        try:
            object.__setattr__(self, "timezone", ZoneInfo(self.timezone_name))
        except (ZoneInfoNotFoundError, KeyError) as e:
            raise ValueError(f"Invalid timezone: {self.timezone_name}") from e
        # Fail at startup, not on every request, when an id list has a typo
        for name in ("allowed_person_ids", "allowed_group_ids"):
            try:
                parse_ids(getattr(self, name))
            except ValueError as e:
                raise ValueError(f"{name.upper()} must be comma-separated numbers, got {getattr(self, name)!r}") from e
        return self


settings = Settings()
