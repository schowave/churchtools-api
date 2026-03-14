import re
from typing import Dict, List, Literal

from pydantic import BaseModel, computed_field, field_validator

from app.utils import parse_iso_datetime

_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class AppointmentData(BaseModel):
    """Structured representation of a ChurchTools appointment for display and export."""

    id: str
    title: str
    start_date: str  # ISO datetime string from API
    end_date: str  # ISO datetime string from API
    meeting_at: str = ""
    information: str = ""
    additional_info: str = ""

    @computed_field
    @property
    def start_date_view(self) -> str:
        return parse_iso_datetime(self.start_date).strftime("%d.%m.%Y")

    @computed_field
    @property
    def start_time_view(self) -> str:
        return parse_iso_datetime(self.start_date).strftime("%H:%M")

    @computed_field
    @property
    def end_time_view(self) -> str:
        return parse_iso_datetime(self.end_date).strftime("%H:%M")


class ColorSettings(BaseModel):
    name: str = "default"
    background_color: str = "#d3d3d3"
    background_alpha: int = 128
    date_color: str = "#c1540c"
    description_color: str = "#4e4e4e"

    @field_validator("background_color", "date_color", "description_color")
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        if not _HEX_COLOR_RE.match(v):
            raise ValueError(f"Invalid hex color: {v!r} (expected format: #rrggbb)")
        return v

    @field_validator("background_alpha")
    @classmethod
    def validate_alpha(cls, v: int) -> int:
        if not (0 <= v <= 255):
            raise ValueError(f"Alpha must be 0–255, got {v}")
        return v


class GenerateRequest(BaseModel):
    """JSON request body for PDF/JPEG generation."""

    type: Literal["pdf", "jpeg"]
    start_date: str
    end_date: str
    calendar_ids: List[str]
    appointment_ids: List[str]
    color_settings: ColorSettings
    additional_infos: Dict[str, str] = {}

    @field_validator("appointment_ids")
    @classmethod
    def validate_appointment_ids(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("At least one appointment must be selected")
        return v
