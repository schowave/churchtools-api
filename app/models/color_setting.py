from sqlalchemy import Column, String, Integer

from app.database import Base


class ColorSetting(Base):
    __tablename__ = "color_settings"

    setting_name = Column(String, primary_key=True)
    background_color = Column(String, nullable=False)
    background_alpha = Column(Integer, nullable=False)
    date_color = Column(String, nullable=False)
    description_color = Column(String, nullable=False)
