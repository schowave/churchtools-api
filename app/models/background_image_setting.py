from sqlalchemy import Column, LargeBinary, String

from app.database import Base


class BackgroundImageSetting(Base):
    __tablename__ = "background_image_settings"

    setting_name = Column(String, primary_key=True)
    image_data = Column(LargeBinary, nullable=False)
    image_filename = Column(String, nullable=False)
