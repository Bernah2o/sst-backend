#!/usr/bin/env python3
"""
Script para crear un usuario administrador en el sistema SST

Uso:
    python create_admin.py

Este script creará un usuario con rol de administrador que puede:
- Gestionar usuarios
- Crear cursos
- Ver reportes
- Acceder a todas las funcionalidades del sistema
"""

import sys
import os
import re
from getpass import getpass

# Agregar el directorio raíz al path para importar los módulos de la app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.database import engine, get_db
from app.models.user import User, UserRole
from app.services.auth import auth_service

def create_admin_user():
    """
    Crear un usuario administrador interactivamente
    """
    print("=" * 50)
    print("CREADOR DE USUARIO ADMINISTRADOR - SISTEMA SST")
    print("=" * 50)
    print()
    
    # Obtener datos del usuario
    print("Ingrese los datos del administrador:")
    print()
    
    email = input("Email: ").strip()
    if not email:
        print("❌ El email es obligatorio")
        return False
    
    # Username field removed - using email as identifier
    
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
            print(f"❌ Ya existe un usuario con ese email, nombre de usuario o documento")
            return False
        
        # Crear el usuario administrador
        hashed_password = auth_service.get_password_hash(password)
        
        admin_user = User(
            email=email,
            hashed_password=hashed_password,
            first_name=first_name,
            last_name=last_name,
            document_type="CC",  # Por defecto Cédula de Ciudadanía
            document_number=document_number,
            phone=phone,
            department=department,
            position=position,
            role=UserRole.ADMIN,  # ¡Rol de administrador!
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

def main():
    """
    Función principal
    """
    try:
        success = create_admin_user()
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