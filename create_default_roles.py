#!/usr/bin/env python3
"""
Script para crear los roles por defecto del sistema.

Este script crea los roles básicos necesarios para el funcionamiento
del sistema SST Platform.
"""

import sys
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno de producción
load_dotenv('.env.production')

# Agregar el directorio raíz al path
sys.path.append(str(Path(__file__).parent))

from sqlalchemy.orm import sessionmaker
from app.database import engine
from app.models.custom_role import CustomRole

def create_default_roles():
    """
    Crear los roles por defecto del sistema
    """
    print("🚀 Creando roles por defecto del sistema")
    print("=" * 50)
    
    # Crear sesión de base de datos
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Definir roles por defecto
        default_roles = [
            {
                "name": "admin",
                "display_name": "Administrador",
                "description": "Administrador del sistema con acceso completo",
                "is_system_role": True
            },
            {
                "name": "supervisor",
                "display_name": "Supervisor",
                "description": "Supervisor con permisos de gestión limitados",
                "is_system_role": True
            },
            {
                "name": "instructor",
                "display_name": "Instructor",
                "description": "Instructor de cursos con permisos de enseñanza",
                "is_system_role": True
            },
            {
                "name": "employee",
                "display_name": "Empleado",
                "description": "Empleado con acceso básico de lectura",
                "is_system_role": True
            }
        ]
        
        created_count = 0
        updated_count = 0
        
        for role_data in default_roles:
            # Verificar si el rol ya existe
            existing_role = db.query(CustomRole).filter(
                CustomRole.name == role_data["name"]
            ).first()
            
            if existing_role:
                # Actualizar rol existente
                existing_role.display_name = role_data["display_name"]
                existing_role.description = role_data["description"]
                existing_role.is_system_role = role_data["is_system_role"]
                updated_count += 1
                print(f"🔄 Rol '{role_data['name']}' actualizado")
            else:
                # Crear nuevo rol
                new_role = CustomRole(
                    name=role_data["name"],
                    display_name=role_data["display_name"],
                    description=role_data["description"],
                    is_system_role=role_data["is_system_role"]
                )
                db.add(new_role)
                created_count += 1
                print(f"✅ Rol '{role_data['name']}' creado")
        
        # Confirmar cambios
        db.commit()
        
        print("\n📊 Resumen:")
        print(f"   • Roles creados: {created_count}")
        print(f"   • Roles actualizados: {updated_count}")
        print(f"   • Total de roles: {len(default_roles)}")
        
        print("\n✅ Roles por defecto configurados exitosamente")
        return True
        
    except Exception as e:
        print(f"❌ Error creando roles: {e}")
        db.rollback()
        return False
        
    finally:
        db.close()

if __name__ == "__main__":
    try:
        success = create_default_roles()
        if success:
            print("\n🎉 Proceso completado exitosamente")
            sys.exit(0)
        else:
            print("\n💥 El proceso falló")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️ Proceso interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Error inesperado: {e}")
        sys.exit(1)