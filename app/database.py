from sqlalchemy import create_engine, Column, String, Integer, Text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import Config
import os

# SQLite database URL
SQLALCHEMY_DATABASE_URL = f"sqlite:///{Config.DB_PATH}"

# Create engine
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

# Database models
class Appointment(Base):
    __tablename__ = "appointments"
    
    id = Column(String, primary_key=True)
    additional_info = Column(Text, nullable=True)

class ColorSetting(Base):
    __tablename__ = "color_settings"
    
    setting_name = Column(String, primary_key=True)
    background_color = Column(String, nullable=False)
    background_alpha = Column(Integer, nullable=False)
    date_color = Column(String, nullable=False)
    description_color = Column(String, nullable=False)

# Dependency for database access
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create schema
def create_schema():
    Base.metadata.create_all(bind=engine)

# CRUD operations for Appointments
def save_additional_infos(db, appointment_info_list):
    try:
        for appointment_id, additional_info in appointment_info_list:
            appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
            if appointment:
                appointment.additional_info = additional_info
            else:
                db.add(Appointment(id=appointment_id, additional_info=additional_info))
        db.commit()
    except Exception as e:
        db.rollback()
        raise e

def get_additional_infos(db, appointment_ids):
    try:
        results = db.query(Appointment).filter(Appointment.id.in_(appointment_ids)).all()
        return {appointment.id: appointment.additional_info for appointment in results}
    except Exception as e:
        print(f"Database error: {e}")
        return {}

# CRUD operations for ColorSettings
def save_color_settings(db, settings):
    try:
        color_setting = db.query(ColorSetting).filter(ColorSetting.setting_name == settings['name']).first()
        if color_setting:
            color_setting.background_color = settings['background_color']
            color_setting.background_alpha = settings['background_alpha']
            color_setting.date_color = settings['date_color']
            color_setting.description_color = settings['description_color']
        else:
            db.add(ColorSetting(
                setting_name=settings['name'],
                background_color=settings['background_color'],
                background_alpha=settings['background_alpha'],
                date_color=settings['date_color'],
                description_color=settings['description_color']
            ))
        db.commit()
    except Exception as e:
        db.rollback()
        raise e

def load_color_settings(db, setting_name):
    try:
        color_setting = db.query(ColorSetting).filter(ColorSetting.setting_name == setting_name).first()
        if color_setting:
            return {
                'name': color_setting.setting_name,
                'background_color': color_setting.background_color,
                'background_alpha': color_setting.background_alpha,
                'date_color': color_setting.date_color,
                'description_color': color_setting.description_color
            }
        else:
            # Default settings
            return {
                'name': setting_name,
                'background_color': '#ffffff',
                'background_alpha': 128,
                'date_color': '#c1540c',
                'description_color': '#4e4e4e'
            }
    except Exception as e:
        print(f"An error occurred: {e}")
        # Return default settings in case of an error
        return {
            'name': setting_name,
            'background_color': '#ffffff',
            'background_alpha': 128,
            'date_color': '#c1540c',
            'description_color': '#4e4e4e'
        }