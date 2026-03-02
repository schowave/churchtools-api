import logging

from sqlalchemy.exc import SQLAlchemyError

from app.models import Appointment, BackgroundImageSetting, ColorSetting, LogoSetting
from app.schemas import ColorSettings

logger = logging.getLogger(__name__)


def save_additional_infos(db, appointment_info_list):
    try:
        for appointment_id, additional_info in appointment_info_list:
            appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
            if appointment:
                appointment.additional_info = additional_info
            else:
                db.add(Appointment(id=appointment_id, additional_info=additional_info))
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise


def get_additional_infos(db, appointment_ids):
    try:
        results = db.query(Appointment).filter(Appointment.id.in_(appointment_ids)).all()
        return {appointment.id: appointment.additional_info for appointment in results}
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        return {}


def save_color_settings(db, settings: ColorSettings):
    try:
        color_setting = db.query(ColorSetting).filter(ColorSetting.setting_name == settings.name).first()
        if color_setting:
            color_setting.background_color = settings.background_color
            color_setting.background_alpha = settings.background_alpha
            color_setting.date_color = settings.date_color
            color_setting.description_color = settings.description_color
        else:
            db.add(
                ColorSetting(
                    setting_name=settings.name,
                    background_color=settings.background_color,
                    background_alpha=settings.background_alpha,
                    date_color=settings.date_color,
                    description_color=settings.description_color,
                )
            )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise


def load_color_settings(db, setting_name) -> ColorSettings:
    try:
        color_setting = db.query(ColorSetting).filter(ColorSetting.setting_name == setting_name).first()
        if color_setting:
            return ColorSettings(
                name=color_setting.setting_name,
                background_color=color_setting.background_color,
                background_alpha=color_setting.background_alpha,
                date_color=color_setting.date_color,
                description_color=color_setting.description_color,
            )
        else:
            return ColorSettings(name=setting_name)
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        return ColorSettings(name=setting_name)


def save_logo(db, setting_name: str, logo_data: bytes, filename: str):
    try:
        logo = db.query(LogoSetting).filter(LogoSetting.setting_name == setting_name).first()
        if logo:
            logo.logo_data = logo_data
            logo.logo_filename = filename
        else:
            db.add(LogoSetting(setting_name=setting_name, logo_data=logo_data, logo_filename=filename))
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise


def load_logo(db, setting_name: str):
    try:
        logo = db.query(LogoSetting).filter(LogoSetting.setting_name == setting_name).first()
        if logo:
            return logo.logo_data, logo.logo_filename
        return None, None
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        return None, None


def delete_logo(db, setting_name: str):
    try:
        logo = db.query(LogoSetting).filter(LogoSetting.setting_name == setting_name).first()
        if logo:
            db.delete(logo)
            db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise


def save_background_image(db, setting_name: str, image_data: bytes, filename: str):
    try:
        bg = db.query(BackgroundImageSetting).filter(BackgroundImageSetting.setting_name == setting_name).first()
        if bg:
            bg.image_data = image_data
            bg.image_filename = filename
        else:
            db.add(BackgroundImageSetting(setting_name=setting_name, image_data=image_data, image_filename=filename))
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise


def load_background_image(db, setting_name: str):
    try:
        bg = db.query(BackgroundImageSetting).filter(BackgroundImageSetting.setting_name == setting_name).first()
        if bg:
            return bg.image_data, bg.image_filename
        return None, None
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        return None, None


def delete_background_image(db, setting_name: str):
    try:
        bg = db.query(BackgroundImageSetting).filter(BackgroundImageSetting.setting_name == setting_name).first()
        if bg:
            db.delete(bg)
            db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
