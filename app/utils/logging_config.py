import os
import logging


def is_development() -> bool:
    env = os.getenv("ENVIRONMENT", "production").lower()
    debug_mode = os.getenv("DEBUG", "false").lower() == "true"
    return debug_mode or env in {"local", "development", "dev"}


def is_production() -> bool:
    env = os.getenv("ENVIRONMENT", "production").lower()
    debug_mode = os.getenv("DEBUG", "false").lower() == "true"
    return not debug_mode and env == "production"


def effective_log_level() -> int:
    """Compute effective log level based on ENVIRONMENT/DEBUG/LOG_LEVEL.

    - Development: DEBUG
    - Production: ERROR by default unless LOG_LEVEL is explicitly set
    """
    log_level_env = os.getenv("LOG_LEVEL")
    if is_development():
        return logging.DEBUG
    if log_level_env:
        return getattr(logging, log_level_env.upper(), logging.ERROR)
    return logging.ERROR


def configure_logging(
    disable_uvicorn_access: bool = False,
    uvicorn_error_level: int = logging.ERROR,
    format_str: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt: str = '%Y-%m-%d %H:%M:%S',
) -> int:
    """Configure root logging and optionally adjust Uvicorn loggers.

    Returns the effective log level applied.
    """
    level = effective_log_level()
    logging.basicConfig(level=level, format=format_str, datefmt=datefmt)

    if disable_uvicorn_access and is_production():
        logging.getLogger("uvicorn.access").disabled = True
        logging.getLogger("uvicorn.access").setLevel(logging.CRITICAL)
        logging.getLogger("uvicorn.error").setLevel(uvicorn_error_level)

    return level

