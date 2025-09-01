#!/usr/bin/env python3
"""
Script para crear un usuario administrador por defecto en el sistema SST

Este script crea un administrador con credenciales predefinidas:
- Email: admin@sst.com
- Usuario: admin
- Contraseña: admin123
- Rol: ADMIN

Uso:
    python create_default_admin.py
"""

import sys
import os

# Agregar el directorio raíz al path para importar los módulos de la app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.database import engine
from app.models.user import User, UserRole
from app.models.custom_role import CustomRole
from app.services.auth import auth_service

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
        "password": "Admin123!",  # Contraseña que cumple con los nuevos requisitos
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
            print("❌ No se encontró el custom role 'admin'. Ejecute primero create_default_roles.py")
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

def main():
    """
    Función principal
    """
    try:
        success = create_default_admin()
        if success:
            print("🎉 Proceso completado exitosamente")
            sys.exit(0)
        else:
            print("💥 El proceso falló")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Proceso cancelado por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Error inesperado: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()