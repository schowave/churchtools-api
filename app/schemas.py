from pydantic import BaseModel


class ColorSettings(BaseModel):
    name: str
    background_color: str = '#d3d3d3'
    background_alpha: int = 128
    date_color: str = '#c1540c'
    description_color: str = '#4e4e4e'
