#!/usr/bin/env python3
"""
Script Unificado de Backup para SST Platform

Este script permite crear respaldos de la base de datos PostgreSQL
con diferentes opciones de configuración para desarrollo y producción.

Uso:
    python backup.py create --env local
    python backup.py create --env production
    python backup.py create --table usuarios
    python backup.py list
    python backup.py cleanup
    python backup.py verify
"""

import os
import sys
import argparse
import subprocess
import datetime
import gzip
import shutil
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:
    print("Error: python-dotenv no está instalado. Instálalo con: pip install python-dotenv")
    sys.exit(1)

class BackupManager:
    def __init__(self, env: str = "local"):
        """Inicializar el sistema de respaldos"""
        self.env = env
        self.env_file = '.env' if env == 'local' else '.env.production'
        self.load_environment()
        self.setup_directories()
        
    def load_environment(self):
        """Cargar variables de entorno según el entorno"""
        env_path = Path(self.env_file)
        
        if env_path.exists():
            load_dotenv(env_path)
            print(f"[INFO] Cargando configuración desde: {env_path}")
        else:
            print(f"[WARNING] Archivo de configuración no encontrado: {env_path}")
            print("[INFO] Usando variables de entorno del sistema")
        
        # Configuración de base de datos (compatible con ambos formatos)
        if self.env == "production":
            self.db_host = os.getenv('DB_HOST') or os.getenv('POSTGRES_HOST', 'localhost')
            self.db_port = os.getenv('DB_PORT') or os.getenv('POSTGRES_PORT', '5432')
            self.db_name = os.getenv('DB_NAME') or os.getenv('POSTGRES_DB')
            self.db_user = os.getenv('DB_USER') or os.getenv('POSTGRES_USER')
            self.db_password = os.getenv('DB_PASSWORD') or os.getenv('POSTGRES_PASSWORD')
        else:
            self.db_host = os.getenv('POSTGRES_HOST', 'localhost')
            self.db_port = os.getenv('POSTGRES_PORT', '5432')
            self.db_name = os.getenv('POSTGRES_DB')
            self.db_user = os.getenv('POSTGRES_USER')
            self.db_password = os.getenv('POSTGRES_PASSWORD')
        
        # Configuración de respaldos
        self.backup_dir = os.getenv('BACKUP_DIR', 'backups')
        self.backup_compress = os.getenv('BACKUP_COMPRESS', 'true').lower() == 'true'
        self.backup_retention_days = int(os.getenv('BACKUP_RETENTION_DAYS', '30'))
        self.backup_keep_count = int(os.getenv('BACKUP_KEEP_COUNT', '7'))
        
        # Ruta de pg_dump según el entorno
        if self.env == "production" and os.name == 'nt':  # Windows
            self.pg_dump_path = r'C:\Program Files\PostgreSQL\17\bin\pg_dump.exe'
        else:
            self.pg_dump_path = 'pg_dump'
        
        if not all([self.db_host, self.db_name, self.db_user]):
            print("[ERROR] Faltan variables de entorno requeridas para la base de datos")
            sys.exit(1)
            
    def setup_directories(self):
        """Crear directorios de respaldo si no existen"""
        self.backup_path = Path(self.backup_dir)
        self.full_backup_path = self.backup_path / 'full'
        self.logs_path = self.backup_path / 'logs'
        
        for path in [self.full_backup_path, self.logs_path]:
            path.mkdir(parents=True, exist_ok=True)
            print(f"[INFO] Directorio creado/verificado: {path}")
            
    def get_timestamp(self) -> str:
        """Obtener timestamp para nombres de archivo"""
        return datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    
    def get_date_dir(self) -> str:
        """Obtener directorio basado en fecha actual"""
        return datetime.datetime.now().strftime('%Y-%m-%d')
        
    def create_backup(self, table: Optional[str] = None) -> bool:
        """Crear respaldo de la base de datos"""
        timestamp = self.get_timestamp()
        
        if self.env == "production":
            # Para producción, usar formato simple
            if table:
                filename = f"sst_{self.env}_table_{table}_{timestamp}.sql"
            else:
                filename = f"sst_{self.env}_backup_{timestamp}.sql"
            backup_file = self.backup_path / filename
        else:
            # Para desarrollo, usar estructura de directorios por fecha
            date_dir = self.get_date_dir()
            backup_date_path = self.full_backup_path / date_dir
            backup_date_path.mkdir(exist_ok=True)
            
            if table:
                filename = f"{self.db_name}_table_{table}_{timestamp}.sql"
            else:
                filename = f"{self.db_name}_full_{timestamp}.sql"
            backup_file = backup_date_path / filename
        
        log_file = self.logs_path / f"{filename}.log"
        
        print(f"[INFO] Iniciando respaldo {self.env}...")
        print(f"[INFO] Base de datos: {self.db_name}")
        print(f"[INFO] Servidor: {self.db_host}:{self.db_port}")
        print(f"[INFO] Usuario: {self.db_user}")
        print(f"[INFO] Archivo: {backup_file}")
        
        # Construir comando pg_dump
        cmd = [
            self.pg_dump_path,
            '--host', self.db_host,
            '--port', str(self.db_port),
            '--username', self.db_user,
            '--dbname', self.db_name,
            '--verbose'
        ]
        
        if table:
            cmd.extend(['--table', table])
        
        if self.env == "production":
            # Opciones específicas para producción
            cmd.extend([
                '--format=plain',
                '--no-owner',
                '--no-privileges'
            ])
        
        # Configurar variables de entorno para pg_dump
        env = os.environ.copy()
        if self.db_password:
            env['PGPASSWORD'] = self.db_password
        if self.env == "production":
            env['PGOPTIONS'] = '--client-min-messages=warning'
            env['PGCLIENTENCODING'] = 'UTF8'
        
        try:
            print("\n[INFO] Ejecutando pg_dump...")
            
            # Ejecutar pg_dump
            with open(backup_file, 'w') as f_out, open(log_file, 'w') as f_log:
                process = subprocess.run(
                    cmd,
                    stdout=f_out,
                    stderr=f_log,
                    env=env,
                    check=True,
                    timeout=1800  # Timeout de 30 minutos
                )
            
            # Verificar que el archivo se creó correctamente
            if not backup_file.exists() or backup_file.stat().st_size == 0:
                print("[ERROR] El archivo de backup no se creó o está vacío")
                return False
            
            file_size = backup_file.stat().st_size
            print(f"[SUCCESS] Respaldo completado: {backup_file}")
            print(f"[INFO] Tamaño: {file_size / 1024 / 1024:.2f} MB")
            
            # Comprimir si está habilitado
            if self.backup_compress:
                compressed_file = self.compress_file(backup_file)
                if compressed_file:
                    backup_file.unlink()  # Eliminar archivo original
                    compressed_size = compressed_file.stat().st_size
                    compression_ratio = (1 - compressed_size / file_size) * 100
                    print(f"[INFO] Archivo comprimido: {compressed_file}")
                    print(f"[INFO] Tamaño comprimido: {compressed_size / 1024 / 1024:.2f} MB")
                    print(f"[INFO] Compresión: {compression_ratio:.1f}%")
            
            return True
            
        except subprocess.TimeoutExpired:
            print("[ERROR] Timeout en la ejecución del backup")
            return False
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Error al crear respaldo: {e}")
            print(f"[ERROR] Ver logs en: {log_file}")
            return False
        except Exception as e:
            print(f"[ERROR] Error inesperado: {e}")
            return False
            
    def compress_file(self, file_path: Path) -> Optional[Path]:
        """Comprimir archivo usando gzip"""
        compressed_path = file_path.with_suffix(file_path.suffix + '.gz')
        
        try:
            with open(file_path, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            return compressed_path
        except Exception as e:
            print(f"[ERROR] Error al comprimir archivo: {e}")
            return None
            
    def cleanup_old_backups(self):
        """Limpiar respaldos antiguos según la política de retención"""
        if self.env == "production":
            # Para producción, mantener un número específico de backups
            self._cleanup_by_count()
        else:
            # Para desarrollo, limpiar por días
            self._cleanup_by_days()
    
    def _cleanup_by_count(self):
        """Limpiar backups manteniendo solo los más recientes (para producción)"""
        try:
            backup_files = list(self.backup_path.glob(f'sst_{self.env}_backup_*.sql*'))
            
            if len(backup_files) <= self.backup_keep_count:
                print(f"[INFO] Manteniendo {len(backup_files)} backups (límite: {self.backup_keep_count})")
                return
            
            # Ordenar por fecha de modificación (más reciente primero)
            backup_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            
            # Eliminar los más antiguos
            files_to_delete = backup_files[self.backup_keep_count:]
            
            print(f"[INFO] Eliminando {len(files_to_delete)} backups antiguos...")
            
            for file_path in files_to_delete:
                file_path.unlink()
                print(f"[INFO] Eliminado: {file_path.name}")
            
            print(f"[INFO] Limpieza completada. Manteniendo {self.backup_keep_count} backups más recientes")
            
        except Exception as e:
            print(f"[ERROR] Error en limpieza de backups: {e}")
    
    def _cleanup_by_days(self):
        """Limpiar backups por días de retención (para desarrollo)"""
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=self.backup_retention_days)
        
        print(f"[INFO] Limpiando respaldos anteriores a: {cutoff_date.strftime('%Y-%m-%d')}")
        
        deleted_count = 0
        for date_dir in self.full_backup_path.iterdir():
            if date_dir.is_dir():
                try:
                    dir_date = datetime.datetime.strptime(date_dir.name, '%Y-%m-%d')
                    if dir_date < cutoff_date:
                        shutil.rmtree(date_dir)
                        print(f"[INFO] Eliminado: {date_dir}")
                        deleted_count += 1
                except ValueError:
                    # Ignorar directorios que no siguen el formato de fecha
                    continue
        
        print(f"[INFO] Se eliminaron {deleted_count} directorios de respaldos antiguos")
        
    def list_backups(self):
        """Listar respaldos disponibles"""
        print("\n[INFO] Respaldos disponibles:")
        print("=" * 50)
        
        if self.env == "production":
            # Para producción, listar archivos directamente
            backup_files = list(self.backup_path.glob(f'sst_{self.env}_backup_*.sql*'))
            backup_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            
            if not backup_files:
                print("No hay respaldos disponibles")
                return
            
            for backup_file in backup_files:
                size_mb = backup_file.stat().st_size / (1024 * 1024)
                mtime = datetime.datetime.fromtimestamp(backup_file.stat().st_mtime)
                print(f"  - {backup_file.name} ({size_mb:.2f} MB) - {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            # Para desarrollo, listar por directorios de fecha
            if not self.full_backup_path.exists():
                print("No hay respaldos disponibles")
                return
            
            for date_dir in sorted(self.full_backup_path.iterdir(), reverse=True):
                if date_dir.is_dir():
                    print(f"\n  {date_dir.name}:")
                    
                    backup_files = [f for f in date_dir.iterdir() if f.is_file() and not f.name.endswith('.log')]
                    if not backup_files:
                        print("    No hay archivos de backup")
                        continue
                    
                    for backup_file in sorted(backup_files):
                        size_mb = backup_file.stat().st_size / (1024 * 1024)
                        print(f"    - {backup_file.name} ({size_mb:.2f} MB)")
                        
    def verify_backups(self):
        """Verificar la integridad de los respaldos"""
        print("\n[INFO] Verificando integridad de respaldos...")
        print("=" * 50)
        
        verified_count = 0
        error_count = 0
        
        if self.env == "production":
            backup_files = list(self.backup_path.glob(f'sst_{self.env}_backup_*.sql*'))
        else:
            backup_files = []
            for date_dir in self.full_backup_path.iterdir():
                if date_dir.is_dir():
                    backup_files.extend([f for f in date_dir.iterdir() if f.is_file() and not f.name.endswith('.log')])
        
        for backup_file in backup_files:
            if self._verify_backup_integrity(backup_file):
                print(f"[OK] {backup_file.name}")
                verified_count += 1
            else:
                print(f"[ERROR] {backup_file.name}")
                error_count += 1
        
        print(f"\n[INFO] Verificación completada:")
        print(f"[INFO] Archivos válidos: {verified_count}")
        print(f"[INFO] Archivos con errores: {error_count}")
        
        return error_count == 0
    
    def _verify_backup_integrity(self, backup_path: Path) -> bool:
        """Verificar la integridad básica del backup"""
        try:
            if backup_path.suffix == '.gz':
                # Verificar archivo comprimido
                with gzip.open(backup_path, 'rt') as f:
                    first_line = f.readline()
                    if not first_line.startswith('--'):
                        return False
            else:
                # Verificar archivo sin comprimir
                with open(backup_path, 'r') as f:
                    first_line = f.readline()
                    if not first_line.startswith('--'):
                        return False
            
            return True
            
        except Exception:
            return False

def main():
    parser = argparse.ArgumentParser(description='Script unificado de backup para SST Platform')
    
    subparsers = parser.add_subparsers(dest='command', help='Comandos disponibles')
    
    # Comando create
    create_parser = subparsers.add_parser('create', help='Crear un nuevo backup')
    create_parser.add_argument('--env', choices=['local', 'production'], default='local',
                              help='Entorno de la base de datos (default: local)')
    create_parser.add_argument('--table', help='Respaldar solo una tabla específica')
    create_parser.add_argument('--compress', action='store_true',
                              help='Forzar compresión del respaldo')
    
    # Comando list
    list_parser = subparsers.add_parser('list', help='Listar backups disponibles')
    list_parser.add_argument('--env', choices=['local', 'production'], default='local',
                            help='Entorno de los backups a listar (default: local)')
    
    # Comando cleanup
    cleanup_parser = subparsers.add_parser('cleanup', help='Limpiar backups antiguos')
    cleanup_parser.add_argument('--env', choices=['local', 'production'], default='local',
                               help='Entorno de los backups a limpiar (default: local)')
    
    # Comando verify
    verify_parser = subparsers.add_parser('verify', help='Verificar integridad de backups')
    verify_parser.add_argument('--env', choices=['local', 'production'], default='local',
                              help='Entorno de los backups a verificar (default: local)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        backup_manager = BackupManager(args.env)
        
        if args.command == 'create':
            # Forzar compresión si se especifica
            if hasattr(args, 'compress') and args.compress:
                backup_manager.backup_compress = True
            
            success = backup_manager.create_backup(getattr(args, 'table', None))
            if not success:
                sys.exit(1)
                
        elif args.command == 'list':
            backup_manager.list_backups()
            
        elif args.command == 'cleanup':
            backup_manager.cleanup_old_backups()
            
        elif args.command == 'verify':
            success = backup_manager.verify_backups()
            if not success:
                sys.exit(1)
        
        print("\n[SUCCESS] Operación completada exitosamente")
        
    except KeyboardInterrupt:
        print("\n[INFO] Operación cancelada por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Error inesperado: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()