from sqlalchemy import Column, String, Text

from app.database import Base


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(String, primary_key=True)
    additional_info = Column(Text, nullable=True)
