#!/usr/bin/env python3
"""
Script Unificado de Base de Datos para SST Platform

Este script permite verificar, mantener y diagnosticar la base de datos
PostgreSQL tanto en desarrollo como en producción.

Uso:
    python database.py check --env local
    python database.py check --env production
    python database.py tables --env production
    python database.py structure --table users --env production
    python database.py stats --env local
    python database.py health --env production
    python database.py cleanup --env local
"""

import os
import sys
import argparse
import psycopg2
from psycopg2 import sql
from sqlalchemy import create_engine, inspect, MetaData, text
from sqlalchemy.orm import sessionmaker
from pathlib import Path
from typing import Optional, Dict, List

try:
    from dotenv import load_dotenv
except ImportError:
    print("Error: python-dotenv no está instalado. Instálalo con: pip install python-dotenv")
    sys.exit(1)

class DatabaseManager:
    def __init__(self, env: str = "local"):
        """Inicializar el gestor de base de datos"""
        self.env = env
        self.env_file = '.env' if env == 'local' else '.env.production'
        self.load_environment()
        
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
            self.db_port = int(os.getenv('DB_PORT') or os.getenv('POSTGRES_PORT', '5432'))
            self.db_name = os.getenv('DB_NAME') or os.getenv('POSTGRES_DB')
            self.db_user = os.getenv('DB_USER') or os.getenv('POSTGRES_USER')
            self.db_password = os.getenv('DB_PASSWORD') or os.getenv('POSTGRES_PASSWORD')
            self.database_url = os.getenv('DATABASE_URL')
        else:
            self.db_host = os.getenv('POSTGRES_HOST', 'localhost')
            self.db_port = int(os.getenv('POSTGRES_PORT', '5432'))
            self.db_name = os.getenv('POSTGRES_DB')
            self.db_user = os.getenv('POSTGRES_USER')
            self.db_password = os.getenv('POSTGRES_PASSWORD')
            self.database_url = os.getenv('DATABASE_URL')
        
        # Configurar URL de base de datos si no está definida
        if not self.database_url:
            self.database_url = f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
        
        # Configuración de conexión directa para psycopg2
        self.db_config = {
            'host': self.db_host,
            'port': self.db_port,
            'database': self.db_name,
            'user': self.db_user,
            'password': self.db_password
        }
        
        if not all([self.db_host, self.db_name, self.db_user]):
            print("[ERROR] Faltan variables de entorno requeridas para la base de datos")
            sys.exit(1)
            
    def test_connection(self) -> bool:
        """Probar conexión a la base de datos"""
        try:
            print(f"[INFO] Probando conexión a la base de datos {self.env}...")
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Verificar versión de PostgreSQL
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            print(f"[SUCCESS] Conexión exitosa!")
            print(f"[INFO] Versión de PostgreSQL: {version}")
            
            # Información adicional de la base de datos
            cursor.execute("SELECT current_database(), current_user, inet_server_addr(), inet_server_port();")
            db_info = cursor.fetchone()
            print(f"[INFO] Base de datos: {db_info[0]}")
            print(f"[INFO] Usuario: {db_info[1]}")
            if db_info[2]:
                print(f"[INFO] Servidor: {db_info[2]}:{db_info[3]}")
            
            cursor.close()
            conn.close()
            return True
            
        except Exception as e:
            print(f"[ERROR] Error de conexión: {e}")
            return False
            
    def get_tables(self) -> List[str]:
        """Obtener lista de tablas en la base de datos"""
        try:
            engine = create_engine(self.database_url)
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            
            print(f"\n[INFO] Tablas encontradas en {self.env} ({len(tables)}):")
            for table in sorted(tables):
                print(f"  - {table}")
                
            return tables
            
        except Exception as e:
            print(f"[ERROR] Error obteniendo tablas: {e}")
            return []
            
    def get_table_structure(self, table_name: str) -> Optional[Dict]:
        """Obtener estructura detallada de una tabla específica"""
        try:
            engine = create_engine(self.database_url)
            inspector = inspect(engine)
            
            # Verificar que la tabla existe
            tables = inspector.get_table_names()
            if table_name not in tables:
                print(f"[ERROR] La tabla '{table_name}' no existe")
                return None
            
            columns = inspector.get_columns(table_name)
            indexes = inspector.get_indexes(table_name)
            foreign_keys = inspector.get_foreign_keys(table_name)
            primary_key = inspector.get_pk_constraint(table_name)
            unique_constraints = inspector.get_unique_constraints(table_name)
            check_constraints = inspector.get_check_constraints(table_name)
            
            print(f"\n[INFO] Estructura de la tabla '{table_name}':")
            print("  Columnas:")
            for col in columns:
                nullable = "NULL" if col['nullable'] else "NOT NULL"
                default = f" DEFAULT {col['default']}" if col['default'] else ""
                print(f"    - {col['name']}: {col['type']} {nullable}{default}")
                
            if primary_key and primary_key['constrained_columns']:
                print(f"  Clave primaria: {', '.join(primary_key['constrained_columns'])}")
                
            if indexes:
                print("  Índices:")
                for idx in indexes:
                    unique = "UNIQUE " if idx['unique'] else ""
                    print(f"    - {unique}{idx['name']}: {', '.join(idx['column_names'])}")
                    
            if foreign_keys:
                print("  Claves foráneas:")
                for fk in foreign_keys:
                    print(f"    - {', '.join(fk['constrained_columns'])} -> {fk['referred_table']}.{', '.join(fk['referred_columns'])}")
                    
            if unique_constraints:
                print("  Restricciones únicas:")
                for uc in unique_constraints:
                    print(f"    - {uc['name']}: {', '.join(uc['column_names'])}")
                    
            if check_constraints:
                print("  Restricciones de verificación:")
                for cc in check_constraints:
                    print(f"    - {cc['name']}: {cc['sqltext']}")
                    
            return {
                'columns': columns,
                'indexes': indexes,
                'foreign_keys': foreign_keys,
                'primary_key': primary_key,
                'unique_constraints': unique_constraints,
                'check_constraints': check_constraints
            }
            
        except Exception as e:
            print(f"[ERROR] Error obteniendo estructura de {table_name}: {e}")
            return None
            
    def get_database_stats(self):
        """Obtener estadísticas de la base de datos"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            print(f"\n[INFO] Estadísticas de la base de datos {self.env}:")
            
            # Tamaño de la base de datos
            cursor.execute("SELECT pg_size_pretty(pg_database_size(current_database()));")
            db_size = cursor.fetchone()[0]
            print(f"  Tamaño total: {db_size}")
            
            # Número de conexiones
            cursor.execute("""
                SELECT count(*) as total_connections,
                       count(*) FILTER (WHERE state = 'active') as active_connections,
                       count(*) FILTER (WHERE state = 'idle') as idle_connections
                FROM pg_stat_activity 
                WHERE datname = current_database();
            """)
            conn_stats = cursor.fetchone()
            print(f"  Conexiones totales: {conn_stats[0]}")
            print(f"  Conexiones activas: {conn_stats[1]}")
            print(f"  Conexiones inactivas: {conn_stats[2]}")
            
            # Tamaño de tablas principales
            cursor.execute("""
                SELECT schemaname, tablename, 
                       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                       pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
                FROM pg_tables 
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC 
                LIMIT 10;
            """)
            
            table_sizes = cursor.fetchall()
            if table_sizes:
                print("  Tablas más grandes:")
                for table in table_sizes:
                    print(f"    - {table[1]}: {table[2]}")
            
            # Estadísticas de actividad
            cursor.execute("""
                SELECT sum(seq_scan) as seq_scans,
                       sum(seq_tup_read) as seq_tup_read,
                       sum(idx_scan) as idx_scans,
                       sum(idx_tup_fetch) as idx_tup_fetch,
                       sum(n_tup_ins) as inserts,
                       sum(n_tup_upd) as updates,
                       sum(n_tup_del) as deletes
                FROM pg_stat_user_tables;
            """)
            
            activity_stats = cursor.fetchone()
            if activity_stats and any(activity_stats):
                print("  Actividad de tablas:")
                print(f"    - Escaneos secuenciales: {activity_stats[0] or 0}")
                print(f"    - Escaneos por índice: {activity_stats[2] or 0}")
                print(f"    - Inserciones: {activity_stats[4] or 0}")
                print(f"    - Actualizaciones: {activity_stats[5] or 0}")
                print(f"    - Eliminaciones: {activity_stats[6] or 0}")
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"[ERROR] Error obteniendo estadísticas: {e}")
            
    def check_alembic_version(self):
        """Verificar versión de Alembic en la base de datos"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Verificar si existe la tabla alembic_version
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'alembic_version'
                );
            """)
            
            if cursor.fetchone()[0]:
                cursor.execute("SELECT version_num FROM alembic_version;")
                version = cursor.fetchone()
                if version:
                    print(f"\n[INFO] Versión de Alembic en {self.env}: {version[0]}")
                else:
                    print(f"\n[WARNING] Tabla alembic_version existe pero está vacía en {self.env}")
            else:
                print(f"\n[WARNING] Tabla alembic_version no existe en {self.env}")
                
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"[ERROR] Error verificando versión de Alembic: {e}")
            
    def check_critical_tables(self):
        """Verificar existencia de tablas críticas"""
        critical_tables = [
            'users', 'courses', 'enrollments', 'user_material_progress', 
            'user_module_progress', 'workers', 'alembic_version'
        ]
        
        tables = self.get_tables()
        
        print(f"\n[INFO] Verificando tablas críticas en {self.env}:")
        missing_tables = []
        
        for table in critical_tables:
            if table in tables:
                print(f"  ✅ {table} - Existe")
            else:
                print(f"  ❌ {table} - NO EXISTE")
                missing_tables.append(table)
        
        if missing_tables:
            print(f"\n[WARNING] Tablas faltantes: {', '.join(missing_tables)}")
            return False
        else:
            print(f"\n[SUCCESS] Todas las tablas críticas están presentes")
            return True
            
    def health_check(self):
        """Realizar verificación completa de salud de la base de datos"""
        print(f"\n[INFO] Verificación de salud de la base de datos {self.env}")
        print("=" * 60)
        
        checks = {
            'Conexión': self.test_connection(),
            'Tablas críticas': self.check_critical_tables(),
        }
        
        # Verificaciones adicionales
        try:
            self.check_alembic_version()
            self.get_database_stats()
            checks['Estadísticas'] = True
        except:
            checks['Estadísticas'] = False
        
        # Resumen de verificaciones
        print("\n" + "=" * 60)
        print("[INFO] Resumen de verificaciones:")
        
        all_passed = True
        for check_name, result in checks.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"  {check_name}: {status}")
            if not result:
                all_passed = False
        
        if all_passed:
            print(f"\n[SUCCESS] Todas las verificaciones pasaron para {self.env}")
        else:
            print(f"\n[WARNING] Algunas verificaciones fallaron para {self.env}")
            
        return all_passed
        
    def cleanup_database(self):
        """Realizar tareas de limpieza y mantenimiento"""
        if self.env == "production":
            print("[WARNING] Limpieza automática no permitida en producción")
            print("[INFO] Ejecute las tareas de mantenimiento manualmente")
            return
            
        try:
            print(f"\n[INFO] Iniciando limpieza de la base de datos {self.env}...")
            
            engine = create_engine(self.database_url)
            
            with engine.connect() as conn:
                # VACUUM ANALYZE para optimizar tablas
                print("[INFO] Ejecutando VACUUM ANALYZE...")
                conn.execute(text("VACUUM ANALYZE;"))
                conn.commit()
                
                # Reindexar tablas si es necesario
                print("[INFO] Reindexando base de datos...")
                conn.execute(text("REINDEX DATABASE " + self.db_name + ";"))
                conn.commit()
                
            print("[SUCCESS] Limpieza completada")
            
        except Exception as e:
            print(f"[ERROR] Error durante la limpieza: {e}")

def main():
    parser = argparse.ArgumentParser(description='Script unificado de gestión de base de datos para SST Platform')
    
    subparsers = parser.add_subparsers(dest='command', help='Comandos disponibles')
    
    # Comando check
    check_parser = subparsers.add_parser('check', help='Verificar conexión y estado básico')
    check_parser.add_argument('--env', choices=['local', 'production'], default='local',
                             help='Entorno de la base de datos (default: local)')
    
    # Comando tables
    tables_parser = subparsers.add_parser('tables', help='Listar todas las tablas')
    tables_parser.add_argument('--env', choices=['local', 'production'], default='local',
                              help='Entorno de la base de datos (default: local)')
    
    # Comando structure
    structure_parser = subparsers.add_parser('structure', help='Mostrar estructura de una tabla')
    structure_parser.add_argument('--table', required=True, help='Nombre de la tabla')
    structure_parser.add_argument('--env', choices=['local', 'production'], default='local',
                                 help='Entorno de la base de datos (default: local)')
    
    # Comando stats
    stats_parser = subparsers.add_parser('stats', help='Mostrar estadísticas de la base de datos')
    stats_parser.add_argument('--env', choices=['local', 'production'], default='local',
                             help='Entorno de la base de datos (default: local)')
    
    # Comando health
    health_parser = subparsers.add_parser('health', help='Verificación completa de salud')
    health_parser.add_argument('--env', choices=['local', 'production'], default='local',
                              help='Entorno de la base de datos (default: local)')
    
    # Comando cleanup
    cleanup_parser = subparsers.add_parser('cleanup', help='Limpiar y optimizar base de datos (solo local)')
    cleanup_parser.add_argument('--env', choices=['local', 'production'], default='local',
                               help='Entorno de la base de datos (default: local)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        db_manager = DatabaseManager(args.env)
        
        if args.command == 'check':
            success = db_manager.test_connection()
            if success:
                db_manager.check_alembic_version()
            if not success:
                sys.exit(1)
                
        elif args.command == 'tables':
            db_manager.get_tables()
            
        elif args.command == 'structure':
            result = db_manager.get_table_structure(args.table)
            if not result:
                sys.exit(1)
                
        elif args.command == 'stats':
            if not db_manager.test_connection():
                sys.exit(1)
            db_manager.get_database_stats()
            
        elif args.command == 'health':
            success = db_manager.health_check()
            if not success:
                sys.exit(1)
                
        elif args.command == 'cleanup':
            if not db_manager.test_connection():
                sys.exit(1)
            db_manager.cleanup_database()
        
        print("\n[SUCCESS] Operación completada exitosamente")
        
    except KeyboardInterrupt:
        print("\n[INFO] Operación cancelada por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Error inesperado: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()