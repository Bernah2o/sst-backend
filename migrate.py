#!/usr/bin/env python3
"""
Script unificado de migraciones para el sistema SST

Este script combina toda la funcionalidad de migraciones y configuración de base de datos:
- Configurar base de datos local
- Ejecutar migraciones de Alembic
- Comandos de desarrollo
- Verificación de estado

Uso:
    python migrate.py setup                    # Configurar DB local completa
    python migrate.py upgrade [revision]       # Aplicar migraciones
    python migrate.py downgrade [revision]     # Revertir migraciones
    python migrate.py current                  # Mostrar revisión actual
    python migrate.py history                  # Mostrar historial
    python migrate.py revision -m "mensaje"     # Crear nueva migración
    python migrate.py status                   # Mostrar estado del proyecto
    python migrate.py server [--env local]     # Ejecutar servidor
"""

import os
import sys
import logging
import subprocess
import argparse
from pathlib import Path
from typing import Optional
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DatabaseManager:
    """Gestor unificado de base de datos y migraciones"""
    
    def __init__(self, env='local'):
        self.env = env
        self.project_root = Path(__file__).parent
        self.alembic_ini = self.project_root / "alembic.ini"
        self.env_file = f'.env.{env}' if env != 'local' else '.env.local'
        
        # Cargar variables de entorno
        if os.path.exists(self.env_file):
            load_dotenv(self.env_file)
        else:
            print(f"❌ Error: No se encontró {self.env_file}")
            sys.exit(1)
        
        # Verificar que existe alembic.ini
        if not self.alembic_ini.exists():
            raise FileNotFoundError(f"No se encontró alembic.ini en {self.project_root}")
    
    def run_command(self, command, description=None, env_vars=None):
        """Ejecutar comando del sistema"""
        if description:
            print(f"[INFO] {description}...")
        
        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)
        
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, env=env)
            if result.returncode == 0:
                if description:
                    print(f"[OK] {description} completado")
                if result.stdout.strip():
                    print(f"   Output: {result.stdout.strip()}")
                return True
            else:
                if description:
                    print(f"[ERROR] Error en {description}")
                if result.stderr.strip():
                    print(f"   Error: {result.stderr.strip()}")
                return False
        except Exception as e:
            if description:
                print(f"[ERROR] Excepción en {description}: {e}")
            return False
    
    def _run_alembic_command(self, command: list) -> bool:
        """Ejecutar comando de Alembic y manejar errores"""
        try:
            logger.info(f"Ejecutando: alembic {' '.join(command)}")
            
            # Configurar variables de entorno
            env_vars = {'ENV_FILE': self.env_file}
            
            # Intentar diferentes métodos para ejecutar alembic
            cmd_options = [
                ["python", "-m", "alembic"] + command,
                ["alembic"] + command
            ]
            
            # Verificar si es proyecto Poetry
            if (self.project_root / "pyproject.toml").exists():
                cmd_options.insert(0, ["poetry", "run", "alembic"] + command)
            
            last_error = None
            for cmd in cmd_options:
                try:
                    result = subprocess.run(
                        cmd,
                        cwd=self.project_root,
                        capture_output=True,
                        text=True,
                        check=True,
                        env={**os.environ, **env_vars}
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
    
    def check_database_connection(self) -> bool:
        """Verificar conexión a la base de datos"""
        try:
            database_url = os.getenv('DATABASE_URL')
            if not database_url:
                logger.error("DATABASE_URL no está configurada")
                return False
            
            engine = create_engine(database_url)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            engine.dispose()
            logger.info("✓ Conexión a la base de datos exitosa")
            return True
        except Exception as e:
            logger.error(f"✗ Error conectando a la base de datos: {e}")
            return False
    
    def setup_local_database(self):
        """Configurar base de datos local completa"""
        print("[SETUP] Configurando base de datos local para desarrollo")
        print("=" * 60)
        
        # Obtener configuración
        db_name = os.getenv('DB_NAME', 'bd_sst_local')
        db_user = os.getenv('DB_USER', 'postgres')
        db_password = os.getenv('DB_PASSWORD', '1481')
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = os.getenv('DB_PORT', '5432')
        
        print(f"[INFO] Base de datos: {db_name}")
        print(f"[INFO] Usuario: {db_user}")
        print(f"[INFO] Host: {db_host}:{db_port}")
        
        # Paso 1: Verificar conexión a PostgreSQL
        print("\n[INFO] Verificando conexión a PostgreSQL...")
        postgres_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/postgres"
        
        try:
            engine = create_engine(postgres_url)
            with engine.connect() as conn:
                result = conn.execute(text("SELECT version()"))
                version = result.fetchone()[0]
                print(f"[OK] PostgreSQL conectado: {version}")
            engine.dispose()
        except Exception as e:
            print(f"[ERROR] Error conectando a PostgreSQL: {e}")
            return False
        
        # Paso 2: Crear base de datos si no existe
        print(f"\n[INFO] Verificando/creando base de datos '{db_name}'...")
        try:
            engine = create_engine(postgres_url)
            with engine.connect() as conn:
                # Verificar si la base de datos existe
                result = conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'"))
                if result.fetchone():
                    print(f"[OK] Base de datos '{db_name}' ya existe")
                else:
                    # Crear base de datos
                    conn.execute(text("COMMIT"))  # Salir de transacción
                    conn.execute(text(f"CREATE DATABASE {db_name}"))
                    print(f"[OK] Base de datos '{db_name}' creada")
            engine.dispose()
        except Exception as e:
            print(f"[ERROR] Error creando base de datos: {e}")
            return False
        
        # Paso 3: Aplicar migraciones
        print("\n[INFO] Aplicando migraciones de Alembic...")
        if self.upgrade():
            print("[OK] Migraciones aplicadas correctamente")
        else:
            print("[ERROR] Error aplicando migraciones")
            return False
        
        # Paso 4: Verificar estructura de la base de datos
        print("\n[INFO] Verificando estructura de la base de datos...")
        database_url = os.getenv('DATABASE_URL')
        
        try:
            engine = create_engine(database_url)
            with engine.connect() as conn:
                # Obtener lista de tablas
                result = conn.execute(text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    ORDER BY table_name
                """))
                
                tables = [row[0] for row in result]
                print(f"[OK] Base de datos configurada con {len(tables)} tablas:")
                
                for i, table in enumerate(tables, 1):
                    print(f"   {i:2d}. {table}")
                
                # Verificar tabla programas específicamente
                if 'programas' in tables:
                    print("\n[OK] Tabla 'programas' confirmada en base de datos local")
                else:
                    print("\n[WARNING] Tabla 'programas' no encontrada")
            
            engine.dispose()
            
        except Exception as e:
            print(f"[ERROR] Error verificando estructura: {e}")
            return False
        
        print("\n[SUCCESS] Base de datos local configurada exitosamente!")
        print("\n[INFO] Próximos pasos:")
        print("   1. Usar: python migrate.py server")
        print("   2. Para migraciones: python migrate.py upgrade")
        print("   3. Para crear migraciones: python migrate.py revision -m 'descripción'")
        
        return True
    
    def upgrade(self, revision: str = "head") -> bool:
        """Ejecutar migraciones hacia adelante"""
        logger.info(f"Iniciando upgrade a revisión: {revision}")
        
        # Verificar conexión antes de migrar
        if not self.check_database_connection():
            return False
        
        # Obtener revisión actual
        current = self.get_current_revision()
        if current:
            logger.info(f"Revisión actual: {current}")
        
        # Ejecutar upgrade
        success = self._run_alembic_command(["upgrade", revision])
        
        if success:
            logger.info(f"✓ Upgrade completado exitosamente")
            # Mostrar nueva revisión
            new_current = self.get_current_revision()
            if new_current and new_current != current:
                logger.info(f"Nueva revisión: {new_current}")
        else:
            logger.error("✗ Error durante el upgrade")
        
        return success
    
    def downgrade(self, revision: str) -> bool:
        """Ejecutar migraciones hacia atrás"""
        logger.info(f"Iniciando downgrade a revisión: {revision}")
        
        # Verificar conexión antes de migrar
        if not self.check_database_connection():
            return False
        
        # Obtener revisión actual
        current = self.get_current_revision()
        if current:
            logger.info(f"Revisión actual: {current}")
        
        # Confirmar downgrade
        if revision == "-1":
            confirm = input("⚠️  ¿Está seguro de revertir la última migración? (y/N): ")
        else:
            confirm = input(f"⚠️  ¿Está seguro de revertir a la revisión {revision}? (y/N): ")
        
        if confirm.lower() != 'y':
            logger.info("Downgrade cancelado")
            return False
        
        # Ejecutar downgrade
        success = self._run_alembic_command(["downgrade", revision])
        
        if success:
            logger.info(f"✓ Downgrade completado exitosamente")
            # Mostrar nueva revisión
            new_current = self.get_current_revision()
            if new_current:
                logger.info(f"Nueva revisión: {new_current}")
        else:
            logger.error("✗ Error durante el downgrade")
        
        return success
    
    def get_current_revision(self) -> Optional[str]:
        """Obtener la revisión actual de la base de datos"""
        try:
            env_vars = {'ENV_FILE': self.env_file}
            cmd_options = [
                ["python", "-m", "alembic", "current"],
                ["alembic", "current"]
            ]
            
            if (self.project_root / "pyproject.toml").exists():
                cmd_options.insert(0, ["poetry", "run", "alembic", "current"])
            
            for cmd_option in cmd_options:
                try:
                    result = subprocess.run(
                        cmd_option,
                        cwd=self.project_root,
                        capture_output=True,
                        text=True,
                        check=True,
                        env={**os.environ, **env_vars}
                    )
                    return result.stdout.strip()
                except (subprocess.CalledProcessError, FileNotFoundError):
                    continue
            
            return None
        except Exception:
            return None
    
    def current(self) -> bool:
        """Mostrar la revisión actual"""
        return self._run_alembic_command(["current"])
    
    def history(self) -> bool:
        """Mostrar historial de migraciones"""
        return self._run_alembic_command(["history"])
    
    def revision(self, message: str, autogenerate: bool = True) -> bool:
        """Crear nueva migración"""
        cmd = ["revision"]
        if autogenerate:
            cmd.append("--autogenerate")
        cmd.extend(["-m", message])
        
        return self._run_alembic_command(cmd)
    
    def run_server(self):
        """Ejecutar servidor con entorno específico"""
        if not os.path.exists(self.env_file):
            print(f"❌ Error: No se encontró {self.env_file}")
            return False
        
        print(f"🚀 Iniciando servidor con {self.env_file}...")
        command = f"uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --env-file {self.env_file}"
        return self.run_command(command)
    
    def show_status(self):
        """Mostrar estado actual del proyecto"""
        print("📊 Estado del proyecto")
        print("=" * 50)
        
        # Verificar archivos de configuración
        config_files = ['.env.local', '.env.production']
        print("📁 Archivos de configuración:")
        for config in config_files:
            status = "✅" if os.path.exists(config) else "❌"
            print(f"   {status} {config}")
        
        # Verificar estado de Alembic para cada entorno
        print("\n🔧 Estado de migraciones:")
        for env in ['local', 'production']:
            env_file = f'.env.{env}' if env != 'production' else '.env.production'
            if os.path.exists(env_file):
                print(f"\n   📍 Entorno: {env}")
                temp_manager = DatabaseManager(env)
                current = temp_manager.get_current_revision()
                if current:
                    print(f"   Revisión actual: {current}")
                else:
                    print(f"   ❌ No se pudo obtener revisión actual")
            else:
                print(f"   ❌ {env}: archivo de configuración no encontrado")
        
        # Verificar conexión a base de datos actual
        print(f"\n🔗 Conexión a base de datos ({self.env}):")
        if self.check_database_connection():
            print("   ✅ Conexión exitosa")
        else:
            print("   ❌ Error de conexión")

def main():
    """Función principal con argumentos de línea de comandos"""
    parser = argparse.ArgumentParser(
        description="Script unificado de migraciones para el sistema SST",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python migrate.py setup                    # Configurar DB local completa
  python migrate.py upgrade                  # Aplicar todas las migraciones
  python migrate.py upgrade +1               # Aplicar siguiente migración
  python migrate.py downgrade -1             # Revertir última migración
  python migrate.py current                  # Mostrar revisión actual
  python migrate.py history                  # Mostrar historial
  python migrate.py revision -m "mensaje"     # Crear nueva migración
  python migrate.py status                   # Mostrar estado del proyecto
  python migrate.py server --env local       # Ejecutar servidor
        """
    )
    
    parser.add_argument(
        '--env',
        default='local',
        choices=['local', 'production'],
        help='Entorno a usar (default: local)'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Comandos disponibles')
    
    # Comando setup
    subparsers.add_parser('setup', help='Configurar base de datos local completa')
    
    # Comando upgrade
    upgrade_parser = subparsers.add_parser('upgrade', help='Aplicar migraciones')
    upgrade_parser.add_argument('revision', nargs='?', default='head', help='Revisión objetivo (default: head)')
    
    # Comando downgrade
    downgrade_parser = subparsers.add_parser('downgrade', help='Revertir migraciones')
    downgrade_parser.add_argument('revision', help='Revisión objetivo (ej: -1, base, revision_id)')
    
    # Comando current
    subparsers.add_parser('current', help='Mostrar revisión actual')
    
    # Comando history
    subparsers.add_parser('history', help='Mostrar historial de migraciones')
    
    # Comando revision
    revision_parser = subparsers.add_parser('revision', help='Crear nueva migración')
    revision_parser.add_argument('-m', '--message', required=True, help='Mensaje de la migración')
    revision_parser.add_argument('--no-autogenerate', action='store_true', help='No usar autogenerate')
    
    # Comando status
    subparsers.add_parser('status', help='Mostrar estado del proyecto')
    
    # Comando server
    subparsers.add_parser('server', help='Ejecutar servidor de desarrollo')
    
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
    
    args = parser.parse_args()
    
    try:
        # Crear manager con el entorno especificado
        manager = DatabaseManager(args.env)
        success = False
        
        if args.command == 'setup':
            if args.env != 'local':
                print("❌ El comando setup solo está disponible para entorno local")
                sys.exit(1)
            success = manager.setup_local_database()
        elif args.command == 'upgrade':
            success = manager.upgrade(args.revision)
        elif args.command == 'downgrade':
            success = manager.downgrade(args.revision)
        elif args.command == 'current':
            success = manager.current()
        elif args.command == 'history':
            success = manager.history()
        elif args.command == 'revision':
            success = manager.revision(args.message, not args.no_autogenerate)
        elif args.command == 'status':
            manager.show_status()
            success = True
        elif args.command == 'server':
            success = manager.run_server()
        
        if success:
            print("\n🎉 Proceso completado exitosamente")
            sys.exit(0)
        else:
            print("\n💥 El proceso falló")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Proceso cancelado por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Error inesperado: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()