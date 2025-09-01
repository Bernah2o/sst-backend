#!/usr/bin/env python3
"""
Script para verificar la estructura de la base de datos de producción
y compararla con los modelos locales.
"""

import os
import sys
import psycopg2
from psycopg2 import sql
from sqlalchemy import create_engine, inspect, MetaData
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Cargar variables de entorno desde .env.production
load_dotenv('.env.production')

# Credenciales de producción desde variables de entorno
PROD_DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD')
}

PROD_DATABASE_URL = os.getenv('DATABASE_URL')

def test_connection():
    """Probar conexión a la base de datos de producción"""
    try:
        print("🔍 Probando conexión a la base de datos de producción...")
        conn = psycopg2.connect(**PROD_DB_CONFIG)
        cursor = conn.cursor()
        
        # Verificar versión de PostgreSQL
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"✅ Conexión exitosa!")
        print(f"📊 Versión de PostgreSQL: {version}")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return False

def get_production_tables():
    """Obtener lista de tablas en producción"""
    try:
        engine = create_engine(PROD_DATABASE_URL)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        print(f"\n📋 Tablas encontradas en producción ({len(tables)}):")
        for table in sorted(tables):
            print(f"  - {table}")
            
        return tables
        
    except Exception as e:
        print(f"❌ Error obteniendo tablas: {e}")
        return []

def get_table_structure(table_name):
    """Obtener estructura de una tabla específica"""
    try:
        engine = create_engine(PROD_DATABASE_URL)
        inspector = inspect(engine)
        
        columns = inspector.get_columns(table_name)
        indexes = inspector.get_indexes(table_name)
        foreign_keys = inspector.get_foreign_keys(table_name)
        
        print(f"\n🔍 Estructura de la tabla '{table_name}':")
        print("  Columnas:")
        for col in columns:
            nullable = "NULL" if col['nullable'] else "NOT NULL"
            default = f" DEFAULT {col['default']}" if col['default'] else ""
            print(f"    - {col['name']}: {col['type']} {nullable}{default}")
            
        if indexes:
            print("  Índices:")
            for idx in indexes:
                print(f"    - {idx['name']}: {idx['column_names']}")
                
        if foreign_keys:
            print("  Claves foráneas:")
            for fk in foreign_keys:
                print(f"    - {fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']}")
                
        return {
            'columns': columns,
            'indexes': indexes,
            'foreign_keys': foreign_keys
        }
        
    except Exception as e:
        print(f"❌ Error obteniendo estructura de {table_name}: {e}")
        return None

def check_alembic_version():
    """Verificar versión de Alembic en producción"""
    try:
        conn = psycopg2.connect(**PROD_DB_CONFIG)
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
                print(f"\n🔄 Versión de Alembic en producción: {version[0]}")
            else:
                print("\n⚠️  Tabla alembic_version existe pero está vacía")
        else:
            print("\n❌ Tabla alembic_version no existe en producción")
            
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error verificando versión de Alembic: {e}")

def main():
    print("🚀 Verificación de Base de Datos de Producción")
    print("=" * 50)
    
    # Probar conexión
    if not test_connection():
        print("\n❌ No se pudo conectar a la base de datos de producción")
        return
    
    # Verificar versión de Alembic
    check_alembic_version()
    
    # Obtener tablas
    tables = get_production_tables()
    
    if not tables:
        print("\n⚠️  No se encontraron tablas en la base de datos")
        return
    
    # Verificar tablas críticas
    critical_tables = ['users', 'courses', 'enrollments', 'user_material_progress', 'user_module_progress', 'workers']
    
    print("\n🔍 Verificando tablas críticas:")
    for table in critical_tables:
        if table in tables:
            print(f"  ✅ {table} - Existe")
            # Obtener estructura de tablas críticas
            get_table_structure(table)
        else:
            print(f"  ❌ {table} - NO EXISTE")
    
    print("\n✅ Verificación completada")

if __name__ == "__main__":
    main()