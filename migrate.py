#!/usr/bin/env python3
"""
Script para ejecutar migraciones de Alembic de forma controlada.

Este script proporciona una interfaz segura para ejecutar migraciones
de base de datos usando Alembic, con validaciones y logging apropiado.

Uso:
    python migrate.py upgrade          # Ejecutar todas las migraciones pendientes
    python migrate.py upgrade +1       # Ejecutar solo la siguiente migración
    python migrate.py downgrade -1     # Revertir la última migración
    python migrate.py current          # Mostrar la revisión actual
    python migrate.py history          # Mostrar historial de migraciones
    python migrate.py check            # Verificar estado de la base de datos
"""

import os
import sys
import logging
import subprocess
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Cargar variables de entorno de producción
load_dotenv('.env.production')

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MigrationManager:
    """Gestor de migraciones de Alembic"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.alembic_ini = self.project_root / "alembic.ini"
        
        # Verificar que existe alembic.ini
        if not self.alembic_ini.exists():
            raise FileNotFoundError(f"No se encontró alembic.ini en {self.project_root}")
    
    def _run_alembic_command(self, command: list) -> bool:
        """Ejecutar comando de Alembic y manejar errores"""
        try:
            logger.info(f"Ejecutando: alembic {' '.join(command)}")
            
            # Intentar diferentes métodos para ejecutar alembic
            cmd_options = []
            if self._is_poetry_project():
                cmd_options.append(["poetry", "run", "alembic"] + command)
            cmd_options.extend([
                ["python", "-m", "alembic"] + command,
                ["alembic"] + command
            ])
            
            last_error = None
            for cmd in cmd_options:
                try:
                    result = subprocess.run(
                        cmd,
                        cwd=self.project_root,
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    
                    if result.stdout:
                        logger.info(f"Salida: {result.stdout.strip()}")
                        
                    return True
                    
                except (subprocess.CalledProcessError, FileNotFoundError) as e:
                    last_error = e
                    continue
            
            # Si llegamos aquí, ningún método funcionó
            if isinstance(last_error, subprocess.CalledProcessError):
                logger.error(f"Error ejecutando comando de Alembic: {last_error}")
                if last_error.stdout:
                    logger.error(f"Stdout: {last_error.stdout}")
                if last_error.stderr:
                    logger.error(f"Stderr: {last_error.stderr}")
            else:
                logger.error("No se pudo ejecutar Alembic con ningún método disponible")
            return False
            
        except Exception as e:
            logger.error(f"Error inesperado: {e}")
            return False
    
    def _is_poetry_project(self) -> bool:
        """Verificar si es un proyecto Poetry"""
        return (self.project_root / "pyproject.toml").exists()
    
    def check_database_connection(self) -> bool:
        """Verificar conexión a la base de datos"""
        try:
            from app.database import engine
            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("✓ Conexión a la base de datos exitosa")
            return True
        except Exception as e:
            logger.error(f"✗ Error conectando a la base de datos: {e}")
            return False
    
    def get_current_revision(self) -> Optional[str]:
        """Obtener la revisión actual de la base de datos"""
        try:
            cmd = ["current"]
            
            # Intentar diferentes métodos para ejecutar alembic
            cmd_options = []
            if self._is_poetry_project():
                cmd_options.append(["poetry", "run", "alembic"] + cmd)
            cmd_options.extend([
                ["python", "-m", "alembic"] + cmd,
                ["alembic"] + cmd
            ])
            
            for cmd_option in cmd_options:
                try:
                    result = subprocess.run(
                        cmd_option,
                        cwd=self.project_root,
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    return result.stdout.strip()
                except (subprocess.CalledProcessError, FileNotFoundError):
                    continue
            
            return None
        except Exception:
            return None
    
    def upgrade(self, revision: str = "head") -> bool:
        """Ejecutar migraciones hacia adelante"""
        logger.info(f"Iniciando upgrade a revisión: {revision}")
        
        # Verificar conexión antes de migrar
        if not self.check_database_connection():
            return False
        
        # Mostrar revisión actual
        current = self.get_current_revision()
        if current:
            logger.info(f"Revisión actual: {current}")
        
        # Ejecutar upgrade
        success = self._run_alembic_command(["upgrade", revision])
        
        if success:
            logger.info("✓ Migraciones ejecutadas exitosamente")
            # Mostrar nueva revisión
            new_current = self.get_current_revision()
            if new_current:
                logger.info(f"Nueva revisión: {new_current}")
        else:
            logger.error("✗ Error ejecutando migraciones")
        
        return success
    
    def downgrade(self, revision: str) -> bool:
        """Revertir migraciones"""
        logger.warning(f"Iniciando downgrade a revisión: {revision}")
        logger.warning("¡ADVERTENCIA! Esta operación puede causar pérdida de datos")
        
        # Verificar conexión antes de migrar
        if not self.check_database_connection():
            return False
        
        # Mostrar revisión actual
        current = self.get_current_revision()
        if current:
            logger.info(f"Revisión actual: {current}")
        
        # Ejecutar downgrade
        success = self._run_alembic_command(["downgrade", revision])
        
        if success:
            logger.info("✓ Downgrade ejecutado exitosamente")
            # Mostrar nueva revisión
            new_current = self.get_current_revision()
            if new_current:
                logger.info(f"Nueva revisión: {new_current}")
        else:
            logger.error("✗ Error ejecutando downgrade")
        
        return success
    
    def current(self) -> bool:
        """Mostrar revisión actual"""
        return self._run_alembic_command(["current"])
    
    def history(self) -> bool:
        """Mostrar historial de migraciones"""
        return self._run_alembic_command(["history"])
    
    def check(self) -> bool:
        """Verificar estado de la base de datos y migraciones"""
        logger.info("Verificando estado de la base de datos...")
        
        # Verificar conexión
        if not self.check_database_connection():
            return False
        
        # Mostrar revisión actual
        logger.info("Revisión actual:")
        self.current()
        
        # Verificar migraciones pendientes comparando current con heads
        logger.info("\nVerificando migraciones pendientes...")
        try:
            # Obtener revisión actual
            current_revision = self.get_current_revision()
            if not current_revision:
                logger.warning("⚠ No se pudo obtener la revisión actual")
                return True
            
            # Obtener heads (últimas migraciones disponibles)
            cmd = ["heads"]
            cmd_options = []
            if self._is_poetry_project():
                cmd_options.append(["poetry", "run", "alembic"] + cmd)
            cmd_options.extend([
                ["python", "-m", "alembic"] + cmd,
                ["alembic"] + cmd
            ])
            
            result = None
            for cmd_option in cmd_options:
                try:
                    result = subprocess.run(
                        cmd_option,
                        cwd=self.project_root,
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    break
                except (subprocess.CalledProcessError, FileNotFoundError):
                    continue
            
            if result is None:
                logger.error("No se pudo ejecutar alembic heads")
                return False
            
            heads_output = result.stdout.strip()
            
            # Extraer el ID de la revisión actual (sin el texto "(head)")
            current_id = current_revision.split()[0] if current_revision else ""
            
            # Verificar si la revisión actual está en heads
            if current_id in heads_output:
                logger.info("✓ Base de datos actualizada - No hay migraciones pendientes")
            else:
                logger.warning("⚠ Hay migraciones pendientes")
                logger.info(f"Revisión actual: {current_revision}")
                logger.info(f"Heads disponibles: {heads_output}")
        
        except Exception as e:
            logger.error(f"Error verificando migraciones: {e}")
            return False
        
        return True


def main():
    """Función principal"""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    command = sys.argv[1]
    manager = MigrationManager()
    
    try:
        if command == "upgrade":
            revision = sys.argv[2] if len(sys.argv) > 2 else "head"
            success = manager.upgrade(revision)
        elif command == "downgrade":
            if len(sys.argv) < 3:
                logger.error("Debe especificar una revisión para downgrade")
                sys.exit(1)
            revision = sys.argv[2]
            success = manager.downgrade(revision)
        elif command == "current":
            success = manager.current()
        elif command == "history":
            success = manager.history()
        elif command == "check":
            success = manager.check()
        else:
            logger.error(f"Comando no reconocido: {command}")
            print(__doc__)
            sys.exit(1)
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        logger.info("\nOperación cancelada por el usuario")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error inesperado: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()