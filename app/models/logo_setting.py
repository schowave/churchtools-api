from sqlalchemy import Column, LargeBinary, String

from app.database import Base


class LogoSetting(Base):
    __tablename__ = "logo_settings"

    setting_name = Column(String, primary_key=True)
    logo_data = Column(LargeBinary, nullable=False)
    logo_filename = Column(String, nullable=False)
