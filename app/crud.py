import structlog
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Appointment, BackgroundImageSetting, ColorSetting, LogoSetting
from app.schemas import ColorSettings

logger = structlog.get_logger()


def save_additional_infos(db: Session, appointment_info_list: list[tuple[str, str]]) -> None:
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


def get_additional_infos(db: Session, appointment_ids: list[str]) -> dict[str, str]:
    try:
        results = db.query(Appointment).filter(Appointment.id.in_(appointment_ids)).all()
        return {appointment.id: appointment.additional_info for appointment in results}
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        return {}


def save_color_settings(db: Session, settings: ColorSettings) -> None:
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


def load_color_settings(db: Session, setting_name: str) -> ColorSettings:
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


def save_logo(db: Session, setting_name: str, logo_data: bytes, filename: str) -> None:
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


def load_logo(db: Session, setting_name: str) -> tuple[bytes | None, str | None]:
    try:
        logo = db.query(LogoSetting).filter(LogoSetting.setting_name == setting_name).first()
        if logo:
            return logo.logo_data, logo.logo_filename
        return None, None
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        return None, None


def delete_logo(db: Session, setting_name: str) -> None:
    try:
        logo = db.query(LogoSetting).filter(LogoSetting.setting_name == setting_name).first()
        if logo:
            db.delete(logo)
            db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise


def save_background_image(db: Session, setting_name: str, image_data: bytes, filename: str) -> None:
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


def load_background_image(db: Session, setting_name: str) -> tuple[bytes | None, str | None]:
    try:
        bg = db.query(BackgroundImageSetting).filter(BackgroundImageSetting.setting_name == setting_name).first()
        if bg:
            return bg.image_data, bg.image_filename
        return None, None
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        return None, None


def delete_background_image(db: Session, setting_name: str) -> None:
    try:
        bg = db.query(BackgroundImageSetting).filter(BackgroundImageSetting.setting_name == setting_name).first()
        if bg:
            db.delete(bg)
            db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise


def list_profiles(db: Session) -> list[str]:
    results = db.query(ColorSetting.setting_name).distinct().all()
    return [r[0] for r in results]


def clone_profile(db: Session, source: str, target: str) -> None:
    source_colors = db.query(ColorSetting).filter(ColorSetting.setting_name == source).first()
    if not source_colors:
        raise ValueError(f"Source profile '{source}' does not exist")

    db.add(
        ColorSetting(
            setting_name=target,
            background_color=source_colors.background_color,
            background_alpha=source_colors.background_alpha,
            date_color=source_colors.date_color,
            description_color=source_colors.description_color,
        )
    )

    source_logo = db.query(LogoSetting).filter(LogoSetting.setting_name == source).first()
    if source_logo:
        db.add(
            LogoSetting(
                setting_name=target,
                logo_data=source_logo.logo_data,
                logo_filename=source_logo.logo_filename,
            )
        )

    source_bg = db.query(BackgroundImageSetting).filter(BackgroundImageSetting.setting_name == source).first()
    if source_bg:
        db.add(
            BackgroundImageSetting(
                setting_name=target,
                image_data=source_bg.image_data,
                image_filename=source_bg.image_filename,
            )
        )

    db.commit()


def delete_profile(db: Session, profile_name: str) -> None:
    if profile_name == "default":
        raise ValueError("Cannot delete the default profile")

    db.query(BackgroundImageSetting).filter(BackgroundImageSetting.setting_name == profile_name).delete()
    db.query(LogoSetting).filter(LogoSetting.setting_name == profile_name).delete()
    db.query(ColorSetting).filter(ColorSetting.setting_name == profile_name).delete()
    db.commit()


def cleanup_orphaned_settings(db: Session) -> None:
    valid_profiles = {r[0] for r in db.query(ColorSetting.setting_name).all()}
    db.query(LogoSetting).filter(~LogoSetting.setting_name.in_(valid_profiles)).delete(synchronize_session=False)
    db.query(BackgroundImageSetting).filter(~BackgroundImageSetting.setting_name.in_(valid_profiles)).delete(
        synchronize_session=False
    )
    db.commit()
