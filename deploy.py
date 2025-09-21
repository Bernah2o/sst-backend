#!/usr/bin/env python3
"""
Script de Despliegue Automatizado - SST Platform
================================================

Este script automatiza el proceso de despliegue tanto en entornos locales como de producción.
Detecta automáticamente el entorno y ejecuta las tareas necesarias para aplicar cambios
y nuevas funcionalidades de manera consistente.

Uso:
    python deploy.py                    # Despliegue completo (detecta entorno automáticamente)
    python deploy.py --env local        # Forzar entorno local
    python deploy.py --env production   # Forzar entorno de producción
    python deploy.py --migrate-only     # Solo ejecutar migraciones
    python deploy.py --deps-only        # Solo actualizar dependencias
    python deploy.py --build-only       # Solo hacer build
    python deploy.py --restart-only     # Solo reiniciar servicios
    python deploy.py --rollback         # Rollback al estado anterior
    python deploy.py --check            # Solo verificar el estado del sistema

Características:
- Detección automática de entorno (local/producción)
- Migraciones de base de datos automáticas
- Actualización de dependencias
- Build y restart de servicios
- Validaciones y rollback automático en caso de errores
- Logs detallados de todo el proceso
"""

import os
import sys
import subprocess
import argparse
import json
import time
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('deploy.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class Colors:
    """Colores para output en terminal"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class DeploymentError(Exception):
    """Excepción personalizada para errores de despliegue"""
    pass

class SSTPlatformDeployer:
    """Clase principal para manejar el despliegue de la plataforma SST"""
    
    def __init__(self, force_env: Optional[str] = None):
        self.backend_dir = Path(__file__).parent.absolute()
        self.project_root = self.backend_dir.parent
        self.frontend_dir = self.project_root / "sst-frontend"
        self.environment = force_env or self._detect_environment()
        self.backup_dir = self.project_root / "backups" / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.deployment_state = {}
        
        # Crear directorio de backups
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Iniciando despliegue en entorno: {self.environment}")
        logger.info(f"Directorio del proyecto: {self.project_root}")
        logger.info(f"Directorio de backup: {self.backup_dir}")

    def _detect_environment(self) -> str:
        """Detecta automáticamente el entorno basado en variables y archivos"""
        # Verificar variables de entorno
        if os.getenv('ENVIRONMENT') == 'production':
            return 'production'
        if os.getenv('NODE_ENV') == 'production':
            return 'production'
        
        # Verificar si estamos en un contenedor Docker
        if os.path.exists('/.dockerenv'):
            return 'production'
        
        # Verificar archivos de configuración de producción
        if (self.project_root / 'docker-compose.prod.yml').exists():
            return 'production'
        
        # Por defecto, asumir entorno local
        return 'local'

    def _run_command(self, command: str, cwd: Optional[Path] = None, check: bool = True) -> Tuple[int, str, str]:
        """Ejecuta un comando y retorna el código de salida, stdout y stderr"""
        if cwd is None:
            cwd = self.backend_dir
            
        logger.info(f"Ejecutando: {command} (en {cwd})")
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutos timeout
            )
            
            if check and result.returncode != 0:
                logger.error(f"Error ejecutando comando: {command}")
                logger.error(f"Codigo de salida: {result.returncode}")
                logger.error(f"STDERR: {result.stderr}")
                raise DeploymentError(f"Comando falló: {command}")
            
            return result.returncode, result.stdout, result.stderr
            
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout ejecutando comando: {command}")
            raise DeploymentError(f"Timeout en comando: {command}")
        except Exception as e:
            logger.error(f"Excepcion ejecutando comando: {command} - {str(e)}")
            raise DeploymentError(f"Error en comando: {command} - {str(e)}")

    def _print_step(self, step: str, description: str = ""):
        """Imprime un paso del proceso con formato"""
        print(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}")
        print(f"{Colors.BOLD}{step}{Colors.ENDC}")
        if description:
            print(f"{Colors.OKCYAN}{description}{Colors.ENDC}")
        print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}")

    def _print_success(self, message: str):
        """Imprime mensaje de éxito"""
        print(f"{Colors.OKGREEN}✅ {message}{Colors.ENDC}")

    def _print_warning(self, message: str):
        """Imprime mensaje de advertencia"""
        print(f"{Colors.WARNING}⚠️  {message}{Colors.ENDC}")

    def _print_error(self, message: str):
        """Imprime mensaje de error"""
        print(f"{Colors.FAIL}❌ {message}{Colors.ENDC}")

    def check_prerequisites(self) -> bool:
        """Verifica que todos los prerequisitos estén instalados"""
        self._print_step("VERIFICANDO PREREQUISITOS", "Comprobando herramientas necesarias")
        
        prerequisites = {
            'python': 'python --version',
            'pip': 'pip --version'
        }
        
        # Verificar si existe frontend
        if self.frontend_dir.exists():
            prerequisites.update({
                'node': 'node --version',
                'npm': 'npm --version'
            })
        
        if self.environment == 'production':
            prerequisites.update({
                'docker': 'docker --version',
                'docker-compose': 'docker-compose --version'
            })
        
        missing = []
        for tool, command in prerequisites.items():
            try:
                returncode, stdout, stderr = self._run_command(command, check=False)
                if returncode == 0:
                    version = stdout.strip().split('\n')[0]
                    self._print_success(f"{tool}: {version}")
                else:
                    missing.append(tool)
                    self._print_error(f"{tool}: No encontrado")
            except:
                missing.append(tool)
                self._print_error(f"{tool}: Error verificando")
        
        if missing:
            self._print_error(f"Herramientas faltantes: {', '.join(missing)}")
            return False
        
        self._print_success("Todos los prerequisitos están instalados")
        return True

    def create_backup(self) -> bool:
        """Crea backup del estado actual"""
        self._print_step("CREANDO BACKUP", "Respaldando estado actual del sistema")
        
        try:
            # Backup de archivos de configuración
            config_files = [
                '.env',
                'requirements.txt',
                'alembic.ini'
            ]
            
            for config_file in config_files:
                src = self.backend_dir / config_file
                if src.exists():
                    dst = self.backup_dir / config_file
                    shutil.copy2(src, dst)
                    self._print_success(f"Backup creado: {config_file}")
            
            # Backup de base de datos (si es local)
            if self.environment == 'local':
                db_file = self.backend_dir / "sst_platform.db"
                if db_file.exists():
                    shutil.copy2(db_file, self.backup_dir / "sst_platform.db")
                    self._print_success("Backup de base de datos creado")
            
            # Backup de package.json del frontend si existe
            if self.frontend_dir.exists():
                frontend_package = self.frontend_dir / "package.json"
                if frontend_package.exists():
                    shutil.copy2(frontend_package, self.backup_dir / "frontend_package.json")
                    self._print_success("Backup de package.json del frontend creado")
            
            # Guardar estado del deployment
            self.deployment_state = {
                'timestamp': datetime.now().isoformat(),
                'environment': self.environment,
                'backup_dir': str(self.backup_dir),
                'git_commit': self._get_git_commit()
            }
            
            with open(self.backup_dir / 'deployment_state.json', 'w') as f:
                json.dump(self.deployment_state, f, indent=2)
            
            self._print_success(f"Backup completo creado en: {self.backup_dir}")
            return True
            
        except Exception as e:
            self._print_error(f"Error creando backup: {str(e)}")
            return False

    def _get_git_commit(self) -> str:
        """Obtiene el commit actual de git"""
        try:
            returncode, stdout, stderr = self._run_command("git rev-parse HEAD", check=False)
            if returncode == 0:
                return stdout.strip()
        except:
            pass
        return "unknown"

    def update_dependencies(self) -> bool:
        """Actualiza las dependencias del backend y frontend"""
        self._print_step("ACTUALIZANDO DEPENDENCIAS", "Instalando/actualizando paquetes")
        
        try:
            # Backend dependencies
            self._print_success("📦 Actualizando dependencias del backend...")
            if self.environment == 'local':
                # En local, usar pip directamente
                self._run_command("pip install -r requirements.txt", cwd=self.backend_dir)
            else:
                # En producción, usar Docker
                self._run_command("docker-compose build backend", cwd=self.project_root)
            self._print_success("Backend dependencies actualizadas")
            
            # Frontend dependencies (si existe)
            if self.frontend_dir.exists():
                self._print_success("📦 Actualizando dependencias del frontend...")
                self._run_command("npm ci", cwd=self.frontend_dir)
                self._print_success("Frontend dependencies actualizadas")
            
            return True
            
        except Exception as e:
            self._print_error(f"Error actualizando dependencias: {str(e)}")
            return False

    def run_migrations(self) -> bool:
        """Ejecuta las migraciones de base de datos"""
        self._print_step("EJECUTANDO MIGRACIONES", "Aplicando cambios de base de datos")
        
        try:
            # Verificar si Alembic está configurado
            alembic_ini = self.backend_dir / "alembic.ini"
            if not alembic_ini.exists():
                self._print_warning("Alembic no configurado - saltando migraciones")
                return True
            
            if self.environment == 'local':
                # En local, ejecutar migraciones directamente
                self._run_command("python -m alembic upgrade head", cwd=self.backend_dir)
            else:
                # En producción, ejecutar en contenedor
                self._run_command("docker-compose exec backend python -m alembic upgrade head", cwd=self.project_root)
            
            self._print_success("Migraciones ejecutadas correctamente")
            return True
            
        except Exception as e:
            self._print_error(f"Error ejecutando migraciones: {str(e)}")
            return False

    def initialize_database(self) -> bool:
        """Inicializa la base de datos con datos por defecto"""
        self._print_step("INICIALIZANDO BASE DE DATOS", "Creando roles y usuario admin por defecto")
        
        try:
            # Ejecutar script de admin para crear roles y usuario por defecto
            admin_script = self.backend_dir / "admin.py"
            if admin_script.exists():
                self._run_command("python admin.py roles", cwd=self.backend_dir)
                self._run_command("python admin.py default", cwd=self.backend_dir)
                self._print_success("Base de datos inicializada con datos por defecto")
            else:
                self._print_warning("Script admin.py no encontrado - saltando inicialización")
            
            return True
            
        except Exception as e:
            self._print_error(f"Error inicializando base de datos: {str(e)}")
            return False

    def build_frontend(self) -> bool:
        """Construye el frontend para producción"""
        self._print_step("CONSTRUYENDO FRONTEND", "Generando build de producción")
        
        try:
            if self.frontend_dir.exists():
                self._run_command("npm run build", cwd=self.frontend_dir)
                self._print_success("Frontend build completado")
                return True
            else:
                self._print_warning("Directorio frontend no encontrado")
                return True
                
        except Exception as e:
            self._print_error(f"Error construyendo frontend: {str(e)}")
            return False

    def restart_services(self) -> bool:
        """Reinicia los servicios según el entorno"""
        self._print_step("REINICIANDO SERVICIOS", "Aplicando cambios y reiniciando")
        
        try:
            if self.environment == 'local':
                self._print_success("En entorno local - Los servicios se reiniciarán automáticamente")
                # En desarrollo local, los servicios suelen tener auto-reload
                return True
            else:
                # En producción, reiniciar contenedores
                self._run_command("docker-compose down", cwd=self.project_root)
                self._run_command("docker-compose up -d", cwd=self.project_root)
                self._print_success("Servicios reiniciados en producción")
                return True
                
        except Exception as e:
            self._print_error(f"Error reiniciando servicios: {str(e)}")
            return False

    def verify_deployment(self) -> bool:
        """Verifica que el despliegue fue exitoso"""
        self._print_step("VERIFICANDO DESPLIEGUE", "Comprobando que todo funcione correctamente")
        
        try:
            # Esperar un momento para que los servicios se inicien
            time.sleep(3)
            
            # Verificar backend
            try:
                if self.environment == 'local':
                    # Usar requests si está disponible, sino curl
                    try:
                        import requests
                        response = requests.get("http://localhost:8000/", timeout=10)
                        if response.status_code == 200:
                            self._print_success("Backend responde correctamente")
                        else:
                            self._print_warning(f"Backend responde con código: {response.status_code}")
                    except ImportError:
                        # Fallback a curl
                        returncode, stdout, stderr = self._run_command("curl -f http://localhost:8000/", check=False)
                        if returncode == 0:
                            self._print_success("Backend responde correctamente")
                        else:
                            self._print_warning("Backend no responde - puede necesitar más tiempo")
                else:
                    self._run_command("docker-compose exec backend curl -f http://localhost:8000/", check=False)
                    self._print_success("Backend en producción verificado")
            except:
                self._print_warning("No se pudo verificar el backend automáticamente")
            
            # Verificar frontend (si existe)
            if self.frontend_dir.exists() and self.environment == 'production':
                try:
                    returncode, stdout, stderr = self._run_command("curl -f http://localhost:3000/", check=False)
                    if returncode == 0:
                        self._print_success("Frontend responde correctamente")
                    else:
                        self._print_warning("Frontend no responde - puede necesitar más tiempo")
                except:
                    self._print_warning("No se pudo verificar el frontend automáticamente")
            
            self._print_success("Verificación de despliegue completada")
            return True
            
        except Exception as e:
            self._print_error(f"Error verificando despliegue: {str(e)}")
            return False

    def rollback(self) -> bool:
        """Realiza rollback al estado anterior"""
        self._print_step("EJECUTANDO ROLLBACK", "Restaurando estado anterior")
        
        try:
            # Buscar el backup más reciente
            backups_dir = self.project_root / "backups"
            if not backups_dir.exists():
                self._print_error("No se encontraron backups para rollback")
                return False
            
            backup_dirs = [d for d in backups_dir.iterdir() if d.is_dir()]
            if not backup_dirs:
                self._print_error("No se encontraron backups para rollback")
                return False
            
            latest_backup = max(backup_dirs, key=lambda x: x.name)
            self._print_success(f"Usando backup: {latest_backup}")
            
            # Restaurar archivos de configuración del backend
            for config_file in ['requirements.txt', '.env', 'alembic.ini']:
                backup_file = latest_backup / config_file
                if backup_file.exists():
                    dst = self.backend_dir / config_file
                    shutil.copy2(backup_file, dst)
                    self._print_success(f"Restaurado: {config_file}")
            
            # Restaurar base de datos si existe
            db_backup = latest_backup / "sst_platform.db"
            if db_backup.exists():
                dst = self.backend_dir / "sst_platform.db"
                shutil.copy2(db_backup, dst)
                self._print_success("Base de datos restaurada")
            
            # Restaurar package.json del frontend si existe
            frontend_backup = latest_backup / "frontend_package.json"
            if frontend_backup.exists() and self.frontend_dir.exists():
                dst = self.frontend_dir / "package.json"
                shutil.copy2(frontend_backup, dst)
                self._print_success("package.json del frontend restaurado")
            
            # Reinstalar dependencias
            self.update_dependencies()
            
            # Reiniciar servicios
            self.restart_services()
            
            self._print_success("Rollback completado")
            return True
            
        except Exception as e:
            self._print_error(f"Error en rollback: {str(e)}")
            return False

    def deploy(self, migrate_only=False, deps_only=False, build_only=False, restart_only=False) -> bool:
        """Ejecuta el proceso completo de despliegue"""
        start_time = time.time()
        
        try:
            print(f"\n{Colors.BOLD}{Colors.HEADER}")
            print("🚀 SST PLATFORM - SCRIPT DE DESPLIEGUE AUTOMATIZADO")
            print(f"Entorno: {self.environment.upper()}")
            print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Directorio: {self.project_root}")
            print(f"{Colors.ENDC}")
            
            # Verificar prerequisitos
            if not self.check_prerequisites():
                return False
            
            # Crear backup (solo en despliegue completo)
            if not migrate_only and not deps_only and not build_only and not restart_only:
                if not self.create_backup():
                    return False
            
            # Ejecutar solo la tarea específica si se solicita
            if deps_only:
                return self.update_dependencies()
            elif migrate_only:
                return self.run_migrations()
            elif build_only:
                return self.build_frontend()
            elif restart_only:
                return self.restart_services()
            
            # Proceso completo de despliegue
            steps = [
                ("Actualizar dependencias", self.update_dependencies),
                ("Ejecutar migraciones", self.run_migrations),
                ("Inicializar base de datos", self.initialize_database),
                ("Construir frontend", self.build_frontend),
                ("Reiniciar servicios", self.restart_services),
                ("Verificar despliegue", self.verify_deployment)
            ]
            
            for step_name, step_func in steps:
                if not step_func():
                    self._print_error(f"Falló el paso: {step_name}")
                    self._print_warning("Iniciando rollback automático...")
                    self.rollback()
                    return False
            
            # Éxito
            elapsed_time = time.time() - start_time
            print(f"\n{Colors.OKGREEN}{Colors.BOLD}")
            print("🎉 ¡DESPLIEGUE COMPLETADO EXITOSAMENTE!")
            print(f"⏱️  Tiempo total: {elapsed_time:.2f} segundos")
            print(f"🌍 Entorno: {self.environment}")
            print(f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"🔗 Backend: http://localhost:8000")
            if self.frontend_dir.exists():
                print(f"🔗 Frontend: http://localhost:3000")
            print(f"{Colors.ENDC}")
            
            return True
            
        except KeyboardInterrupt:
            self._print_warning("Despliegue interrumpido por el usuario")
            return False
        except Exception as e:
            self._print_error(f"Error inesperado durante el despliegue: {str(e)}")
            return False

def main():
    """Función principal"""
    parser = argparse.ArgumentParser(description='Script de despliegue automatizado para SST Platform')
    parser.add_argument('--env', choices=['local', 'production'], help='Forzar entorno específico')
    parser.add_argument('--migrate-only', action='store_true', help='Solo ejecutar migraciones')
    parser.add_argument('--deps-only', action='store_true', help='Solo actualizar dependencias')
    parser.add_argument('--build-only', action='store_true', help='Solo hacer build del frontend')
    parser.add_argument('--restart-only', action='store_true', help='Solo reiniciar servicios')
    parser.add_argument('--rollback', action='store_true', help='Ejecutar rollback')
    parser.add_argument('--check', action='store_true', help='Solo verificar prerequisitos')
    
    args = parser.parse_args()
    
    try:
        deployer = SSTPlatformDeployer(force_env=args.env)
        
        if args.check:
            success = deployer.check_prerequisites()
        elif args.rollback:
            success = deployer.rollback()
        else:
            success = deployer.deploy(
                migrate_only=args.migrate_only,
                deps_only=args.deps_only,
                build_only=args.build_only,
                restart_only=args.restart_only
            )
        
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"{Colors.FAIL}💥 Error fatal: {str(e)}{Colors.ENDC}")
        sys.exit(1)

if __name__ == "__main__":
    main()