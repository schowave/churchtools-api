import structlog
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Appointment, BackgroundImageSetting, ColorSetting, LogoSetting
from app.schemas import ColorSettings

logger = structlog.get_logger()


def save_additional_infos(db: Session, appointment_info_list: list[tuple[str, str]]) -> None:
    if not appointment_info_list:
        return
    rows = [{"id": appointment_id, "additional_info": info} for appointment_id, info in appointment_info_list]
    statement = sqlite_insert(Appointment).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=[Appointment.id], set_={"additional_info": statement.excluded.additional_info}
    )
    try:
        db.execute(statement)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise


def get_additional_infos(db: Session, appointment_ids: list[str]) -> dict[str, str]:
    try:
        results = db.query(Appointment).filter(Appointment.id.in_(appointment_ids)).all()
        return {appointment.id: appointment.additional_info for appointment in results}
    except SQLAlchemyError as e:
        logger.error("database_error", operation="get_additional_infos", error=str(e))
        return {}


def claim_legacy_additional_infos(db: Session, legacy_ids: dict[str, str]) -> dict[str, str]:
    """Move custom texts stored under pre-v7.1 ids to the current ids ({current: legacy}).

    Each legacy row is claimed once and then deleted, so a later load with another date range
    cannot attach it to a different occurrence again.
    """
    if not legacy_ids:
        return {}
    current_by_legacy = {legacy: current for current, legacy in legacy_ids.items()}
    try:
        rows = db.query(Appointment).filter(Appointment.id.in_(current_by_legacy)).all()
        claimed = {current_by_legacy[row.id]: row.additional_info for row in rows if row.additional_info}
        for row in rows:
            db.delete(row)
        db.flush()
        if claimed:
            db.add_all(Appointment(id=current, additional_info=info) for current, info in claimed.items())
        db.commit()
        if rows:
            logger.info("legacy_additional_infos_migrated", claimed=len(claimed), removed=len(rows))
        return claimed
    except SQLAlchemyError as e:
        db.rollback()
        logger.error("database_error", operation="claim_legacy_additional_infos", error=str(e))
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
        logger.error("database_error", operation="load_color_settings", error=str(e))
        return ColorSettings(name=setting_name)


def _save_image(db: Session, model, data_attr: str, filename_attr: str, setting_name: str, data: bytes, filename: str):
    try:
        row = db.query(model).filter(model.setting_name == setting_name).first()
        if row is None:
            row = model(setting_name=setting_name)
            db.add(row)
        setattr(row, data_attr, data)
        setattr(row, filename_attr, filename)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise


def _load_image(db: Session, model, data_attr: str, filename_attr: str, setting_name: str):
    try:
        row = db.query(model).filter(model.setting_name == setting_name).first()
        if row:
            return getattr(row, data_attr), getattr(row, filename_attr)
        return None, None
    except SQLAlchemyError as e:
        logger.error("database_error", operation="load_image", table=model.__tablename__, error=str(e))
        return None, None


def _delete_image(db: Session, model, setting_name: str) -> None:
    try:
        row = db.query(model).filter(model.setting_name == setting_name).first()
        if row:
            db.delete(row)
            db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise


def save_logo(db: Session, setting_name: str, logo_data: bytes, filename: str) -> None:
    _save_image(db, LogoSetting, "logo_data", "logo_filename", setting_name, logo_data, filename)


def load_logo(db: Session, setting_name: str) -> tuple[bytes | None, str | None]:
    return _load_image(db, LogoSetting, "logo_data", "logo_filename", setting_name)


def delete_logo(db: Session, setting_name: str) -> None:
    _delete_image(db, LogoSetting, setting_name)


def save_background_image(db: Session, setting_name: str, image_data: bytes, filename: str) -> None:
    _save_image(db, BackgroundImageSetting, "image_data", "image_filename", setting_name, image_data, filename)


def load_background_image(db: Session, setting_name: str) -> tuple[bytes | None, str | None]:
    return _load_image(db, BackgroundImageSetting, "image_data", "image_filename", setting_name)


def delete_background_image(db: Session, setting_name: str) -> None:
    _delete_image(db, BackgroundImageSetting, setting_name)
