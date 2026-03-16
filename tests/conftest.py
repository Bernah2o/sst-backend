"""
Configuración global de pytest para la suite de tests SST.

Para ejecutar solo los tests de email (sin requerir cobertura del 80%):
    pytest -m email --override-ini="addopts=-ra -v --tb=short -p no:warnings"
"""
import os
import pytest
from pathlib import Path
from dotenv import load_dotenv


def pytest_configure(config):
    """Carga variables de entorno antes de que pytest importe los módulos de la app."""
    env_file = Path(__file__).parent.parent / ".env.production"
    if not env_file.exists():
        env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=False)

    # Garantizar que DATABASE_URL exista para que config.py no falle al importar
    if not os.getenv("DATABASE_URL"):
        os.environ.setdefault("DATABASE_URL", "sqlite:///./test_placeholder.db")
