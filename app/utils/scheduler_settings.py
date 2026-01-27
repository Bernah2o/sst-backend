"""Utilidades para verificar configuración de schedulers"""
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)


def is_scheduler_enabled(db: Session, setting_key: str) -> bool:
    """
    Verifica si un scheduler está habilitado en la configuración del sistema.

    Args:
        db: Sesión de base de datos
        setting_key: Clave del scheduler en SystemSettings

    Returns:
        True si está habilitado, False si no
    """
    from app.models.admin_config import SystemSettings

    try:
        setting = db.query(SystemSettings).filter(
            SystemSettings.key == setting_key
        ).first()

        # Si no existe la configuración, asumimos que está habilitado por defecto
        if not setting:
            return True

        return setting.is_enabled
    except Exception as e:
        logger.error(f"Error verificando estado del scheduler {setting_key}: {e}")
        # En caso de error, permitir ejecución por defecto
        return True


def get_all_scheduler_settings(db: Session) -> dict:
    """
    Obtiene el estado de todos los schedulers configurados.

    Returns:
        Diccionario con el estado de cada scheduler
    """
    from app.models.admin_config import SystemSettings

    scheduler_keys = [
        SystemSettings.EXAM_NOTIFICATIONS_ENABLED,
        SystemSettings.REINDUCTION_SCHEDULER_ENABLED,
        SystemSettings.BIRTHDAY_SCHEDULER_ENABLED,
        SystemSettings.COURSE_REMINDER_SCHEDULER_ENABLED,
    ]

    result = {}
    for key in scheduler_keys:
        setting = db.query(SystemSettings).filter(SystemSettings.key == key).first()
        if setting:
            result[key] = {
                "is_enabled": setting.is_enabled,
                "description": setting.description,
                "updated_at": setting.updated_at,
                "updated_by": setting.updated_by
            }
        else:
            result[key] = {
                "is_enabled": True,  # Por defecto habilitado
                "description": None,
                "updated_at": None,
                "updated_by": None
            }

    return result


def set_scheduler_enabled(db: Session, setting_key: str, enabled: bool, user_id: int = None, description: str = None) -> bool:
    """
    Establece el estado de un scheduler.

    Args:
        db: Sesión de base de datos
        setting_key: Clave del scheduler
        enabled: True para habilitar, False para deshabilitar
        user_id: ID del usuario que hace el cambio
        description: Descripción del scheduler

    Returns:
        True si se actualizó correctamente
    """
    from app.models.admin_config import SystemSettings

    try:
        setting = db.query(SystemSettings).filter(
            SystemSettings.key == setting_key
        ).first()

        if not setting:
            # Crear nuevo registro
            setting = SystemSettings(
                key=setting_key,
                value="true" if enabled else "false",
                description=description,
                is_enabled=enabled,
                updated_by=user_id
            )
            db.add(setting)
        else:
            setting.is_enabled = enabled
            setting.value = "true" if enabled else "false"
            setting.updated_by = user_id
            if description:
                setting.description = description

        db.commit()
        return True
    except Exception as e:
        logger.error(f"Error actualizando estado del scheduler {setting_key}: {e}")
        db.rollback()
        return False
