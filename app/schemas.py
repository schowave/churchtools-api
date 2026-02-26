import re

from pydantic import BaseModel, field_validator

_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class ColorSettings(BaseModel):
    name: str
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
