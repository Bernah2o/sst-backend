#!/usr/bin/env python3
"""
Script unificado de administración para el sistema SST

Este script combina toda la funcionalidad de administración:
- Crear roles por defecto del sistema
- Crear administrador por defecto
- Crear administrador personalizado

Uso:
    python admin.py roles                    # Crear roles por defecto
    python admin.py default                  # Crear admin por defecto
    python admin.py create                   # Crear admin personalizado
    python admin.py setup                    # Configuración completa (roles + admin por defecto)
"""

import sys
import os
import re
import argparse
from getpass import getpass
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv('.env')

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session, sessionmaker
from app.database import engine
from app.models.user import User, UserRole
from app.models.custom_role import CustomRole
from app.services.auth import auth_service

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

def create_default_admin():
    """
    Crear un usuario administrador con datos predefinidos
    """
    print("=" * 50)
    print("CREANDO ADMINISTRADOR POR DEFECTO")
    print("=" * 50)
    print()
    
    # Datos predefinidos del administrador
    admin_data = {
        "email": "bernardino.deaguas@gmail.com",
        "password": "Admin123!",
        "first_name": "Administrador",
        "last_name": "Sistema",
        "document_number": "15172967",
        "phone": "3008054296",
        "department": "Sistemas",
        "position": "Administrador del Sistema"
    }
    
    print("Datos del administrador:")
    print(f"  Email: {admin_data['email']}")
    print(f"  Contraseña: {admin_data['password']}")
    print(f"  Nombre: {admin_data['first_name']} {admin_data['last_name']}")
    print()
    
    # Crear sesión de base de datos
    db = Session(engine)
    
    try:
        # Verificar si el usuario ya existe
        existing_user = db.query(User).filter(
            (User.email == admin_data['email']) | 
            (User.document_number == admin_data['document_number'])
        ).first()
        
        if existing_user:
            print(f"⚠️  Ya existe un usuario administrador:")
            print(f"   ID: {existing_user.id}")
            print(f"   Email: {existing_user.email}")
            print(f"   Rol: {existing_user.role.value}")
            print()
            
            # Si existe pero no es admin, actualizar el rol
            if existing_user.role != UserRole.ADMIN:
                print("🔄 Actualizando rol a ADMIN...")
                existing_user.role = UserRole.ADMIN
                db.commit()
                print("✅ Rol actualizado a ADMIN")
            else:
                print("✅ El usuario ya tiene rol de ADMIN")
            
            return True
        
        # Buscar el custom role de admin
        admin_custom_role = db.query(CustomRole).filter(
            CustomRole.name == "admin"
        ).first()
        
        if not admin_custom_role:
            print("❌ No se encontró el custom role 'admin'. Ejecute primero: python admin.py roles")
            return False
        
        # Crear el usuario administrador
        hashed_password = auth_service.get_password_hash(admin_data['password'])
        
        admin_user = User(
            email=admin_data['email'],
            hashed_password=hashed_password,
            first_name=admin_data['first_name'],
            last_name=admin_data['last_name'],
            document_type="CC",
            document_number=admin_data['document_number'],
            phone=admin_data['phone'],
            department=admin_data['department'],
            position=admin_data['position'],
            role=UserRole.ADMIN,
            custom_role_id=admin_custom_role.id,
            is_active=True,
            is_verified=True
        )
        
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        
        print("✅ Usuario administrador creado exitosamente!")
        print()
        print("Detalles del usuario:")
        print(f"  ID: {admin_user.id}")
        print(f"  Email: {admin_user.email}")
        print(f"  Nombre: {admin_user.full_name}")
        print(f"  Rol: {admin_user.role.value}")
        print(f"  Custom Role: {admin_custom_role.display_name}")
        print(f"  Documento: {admin_user.document_number}")
        print()
        print("🔐 Credenciales de acceso:")
        print(f"   Email: {admin_data['email']}")
        print(f"   Contraseña: {admin_data['password']}")
        print()
        print("⚠️  IMPORTANTE: Cambie la contraseña después del primer inicio de sesión")
        print()
        
        return True
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error al crear el usuario: {str(e)}")
        return False
    
    finally:
        db.close()

def create_custom_admin():
    """
    Crear un usuario administrador interactivamente
    """
    print("=" * 50)
    print("CREADOR DE USUARIO ADMINISTRADOR PERSONALIZADO")
    print("=" * 50)
    print()
    
    # Obtener datos del usuario
    print("Ingrese los datos del administrador:")
    print()
    
    email = input("Email: ").strip()
    if not email:
        print("❌ El email es obligatorio")
        return False
    
    first_name = input("Nombre: ").strip()
    if not first_name:
        print("❌ El nombre es obligatorio")
        return False
    
    last_name = input("Apellido: ").strip()
    if not last_name:
        print("❌ El apellido es obligatorio")
        return False
    
    document_number = input("Número de documento: ").strip()
    if not document_number:
        print("❌ El número de documento es obligatorio")
        return False
    
    # Solicitar contraseña
    while True:
        password = getpass("Contraseña: ")
        
        # Validar longitud mínima
        if len(password) < 8:
            print("❌ La contraseña debe tener al menos 8 caracteres")
            continue
        
        # Validar que contenga al menos una letra
        if not re.search(r'[a-zA-Z]', password):
            print("❌ La contraseña debe contener al menos una letra")
            continue
        
        # Validar que contenga al menos un número
        if not re.search(r'\d', password):
            print("❌ La contraseña debe contener al menos un número")
            continue
        
        # Validar que contenga al menos un carácter especial
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            print("❌ La contraseña debe contener al menos un carácter especial (!@#$%^&*(),.?\":{}|<>)")
            continue
        
        password_confirm = getpass("Confirmar contraseña: ")
        if password != password_confirm:
            print("❌ Las contraseñas no coinciden")
            continue
        
        break
    
    # Datos opcionales
    phone = input("Teléfono (opcional): ").strip() or None
    department = input("Departamento (opcional): ").strip() or None
    position = input("Cargo (opcional): ").strip() or None
    
    # Crear sesión de base de datos
    db = Session(engine)
    
    try:
        # Verificar si el usuario ya existe
        existing_user = db.query(User).filter(
            (User.email == email) |
            (User.document_number == document_number)
        ).first()
        
        if existing_user:
            print(f"❌ Ya existe un usuario con ese email o documento")
            return False
        
        # Crear el usuario administrador
        hashed_password = auth_service.get_password_hash(password)
        
        admin_user = User(
            email=email,
            hashed_password=hashed_password,
            first_name=first_name,
            last_name=last_name,
            document_type="CC",
            document_number=document_number,
            phone=phone,
            department=department,
            position=position,
            role=UserRole.ADMIN,
            is_active=True,
            is_verified=True
        )
        
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        
        print()
        print("✅ Usuario administrador creado exitosamente!")
        print()
        print("Detalles del usuario:")
        print(f"  ID: {admin_user.id}")
        print(f"  Email: {admin_user.email}")
        print(f"  Nombre: {admin_user.full_name}")
        print(f"  Rol: {admin_user.role.value}")
        print(f"  Documento: {admin_user.document_number}")
        print(f"  Activo: {'Sí' if admin_user.is_active else 'No'}")
        print(f"  Verificado: {'Sí' if admin_user.is_verified else 'No'}")
        print()
        print("El usuario puede ahora:")
        print("  • Iniciar sesión en el sistema")
        print("  • Gestionar otros usuarios")
        print("  • Crear y administrar cursos")
        print("  • Ver todos los reportes")
        print("  • Acceder a la configuración del sistema")
        print()
        
        return True
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error al crear el usuario: {str(e)}")
        return False
    
    finally:
        db.close()

def setup_complete():
    """
    Configuración completa: roles + admin por defecto
    """
    print("🚀 CONFIGURACIÓN COMPLETA DEL SISTEMA")
    print("=" * 50)
    print()
    
    # Crear roles primero
    print("Paso 1: Creando roles por defecto...")
    if not create_default_roles():
        print("❌ Error creando roles")
        return False
    
    print("\n" + "=" * 50)
    print("Paso 2: Creando administrador por defecto...")
    if not create_default_admin():
        print("❌ Error creando administrador")
        return False
    
    print("\n" + "=" * 50)
    print("🎉 CONFIGURACIÓN COMPLETA EXITOSA")
    print("=" * 50)
    print()
    print("✅ Sistema listo para usar")
    print("✅ Roles del sistema configurados")
    print("✅ Administrador por defecto creado")
    print()
    
    return True

def main():
    """
    Función principal con argumentos de línea de comandos
    """
    parser = argparse.ArgumentParser(
        description="Script unificado de administración para el sistema SST",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python admin.py roles      # Crear roles por defecto
  python admin.py default    # Crear admin por defecto
  python admin.py create     # Crear admin personalizado
  python admin.py setup      # Configuración completa
        """
    )
    
    parser.add_argument(
        'action',
        choices=['roles', 'default', 'create', 'setup'],
        help='Acción a realizar'
    )
    
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
    
    args = parser.parse_args()
    
    try:
        success = False
        
        if args.action == 'roles':
            success = create_default_roles()
        elif args.action == 'default':
            success = create_default_admin()
        elif args.action == 'create':
            success = create_custom_admin()
        elif args.action == 'setup':
            success = setup_complete()
        
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