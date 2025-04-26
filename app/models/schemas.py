from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class AppointmentBase(BaseModel):
    id: str
    description: str
    startDate: str
    endDate: str
    meetingAt: Optional[str] = ""
    information: Optional[str] = ""
    additional_info: Optional[str] = ""
    startDateView: Optional[str] = None
    startTimeView: Optional[str] = None
    endTimeView: Optional[str] = None
    address: Optional[Dict[str, Any]] = None

    class Config:
        orm_mode = True

class AppointmentList(BaseModel):
    appointments: List[AppointmentBase]

class ColorSettings(BaseModel):
    name: str = "default"
    background_color: str = "#ffffff"
    background_alpha: int = 128
    date_color: str = "#c1540c"
    description_color: str = "#4e4e4e"

    class Config:
        orm_mode = True

class Calendar(BaseModel):
    id: int
    name: str
    isPublic: bool = True

    class Config:
        orm_mode = True

class CalendarList(BaseModel):
    calendars: List[Calendar]

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None