from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import require_admin
from app.models.user import User, UserRole
from app.models.custom_role import CustomRole
from app.schemas.custom_role import (
    CustomRoleCreate, 
    CustomRoleUpdate, 
    CustomRoleResponse, 
    CustomRoleList,
    RolePermissionAssignment
)
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

# Schema para permisos
class Permission(BaseModel):
    id: int
    resource_type: str
    action: str
    description: Optional[str] = None
    is_active: bool = True

    class Config:
        from_attributes = True

# Lista de permisos disponibles en el sistema
PERMISSIONS_DATA = [
    {"id": 1, "resource_type": "user", "action": "create", "description": "Crear usuarios", "is_active": True},
    {"id": 2, "resource_type": "user", "action": "read", "description": "Ver usuarios", "is_active": True},
    {"id": 3, "resource_type": "user", "action": "update", "description": "Actualizar usuarios", "is_active": True},
    {"id": 4, "resource_type": "user", "action": "delete", "description": "Eliminar usuarios", "is_active": True},
    {"id": 5, "resource_type": "course", "action": "create", "description": "Crear cursos", "is_active": True},
    {"id": 6, "resource_type": "course", "action": "read", "description": "Ver cursos", "is_active": True},
    {"id": 7, "resource_type": "course", "action": "update", "description": "Actualizar cursos", "is_active": True},
    {"id": 8, "resource_type": "course", "action": "delete", "description": "Eliminar cursos", "is_active": True},
    {"id": 9, "resource_type": "enrollment", "action": "create", "description": "Crear inscripciones", "is_active": True},
    {"id": 10, "resource_type": "enrollment", "action": "read", "description": "Ver inscripciones", "is_active": True},
    {"id": 11, "resource_type": "enrollment", "action": "update", "description": "Actualizar inscripciones", "is_active": True},
    {"id": 12, "resource_type": "enrollment", "action": "delete", "description": "Eliminar inscripciones", "is_active": True},
    {"id": 13, "resource_type": "evaluation", "action": "create", "description": "Crear evaluaciones", "is_active": True},
    {"id": 14, "resource_type": "evaluation", "action": "read", "description": "Ver evaluaciones", "is_active": True},
    {"id": 15, "resource_type": "evaluation", "action": "update", "description": "Actualizar evaluaciones", "is_active": True},
    {"id": 16, "resource_type": "evaluation", "action": "delete", "description": "Eliminar evaluaciones", "is_active": True},
    {"id": 17, "resource_type": "survey", "action": "create", "description": "Crear encuestas", "is_active": True},
    {"id": 18, "resource_type": "survey", "action": "read", "description": "Ver encuestas", "is_active": True},
    {"id": 19, "resource_type": "survey", "action": "update", "description": "Actualizar encuestas", "is_active": True},
    {"id": 20, "resource_type": "survey", "action": "delete", "description": "Eliminar encuestas", "is_active": True},
    {"id": 21, "resource_type": "certificate", "action": "create", "description": "Crear certificados", "is_active": True},
    {"id": 22, "resource_type": "certificate", "action": "read", "description": "Ver certificados", "is_active": True},
    {"id": 23, "resource_type": "certificate", "action": "update", "description": "Actualizar certificados", "is_active": True},
    {"id": 24, "resource_type": "certificate", "action": "delete", "description": "Eliminar certificados", "is_active": True},
    {"id": 25, "resource_type": "attendance", "action": "create", "description": "Crear registros de asistencia", "is_active": True},
    {"id": 26, "resource_type": "attendance", "action": "read", "description": "Ver asistencia", "is_active": True},
    {"id": 27, "resource_type": "attendance", "action": "update", "description": "Actualizar asistencia", "is_active": True},
    {"id": 28, "resource_type": "attendance", "action": "delete", "description": "Eliminar registros de asistencia", "is_active": True},
    {"id": 29, "resource_type": "report", "action": "create", "description": "Crear reportes", "is_active": True},
    {"id": 30, "resource_type": "report", "action": "read", "description": "Ver reportes", "is_active": True},
    {"id": 31, "resource_type": "notification", "action": "create", "description": "Crear notificaciones", "is_active": True},
    {"id": 32, "resource_type": "notification", "action": "read", "description": "Ver notificaciones", "is_active": True},
    {"id": 33, "resource_type": "notification", "action": "update", "description": "Actualizar notificaciones", "is_active": True},
    {"id": 34, "resource_type": "notification", "action": "delete", "description": "Eliminar notificaciones", "is_active": True},
    {"id": 35, "resource_type": "worker", "action": "create", "description": "Crear trabajadores", "is_active": True},
    {"id": 36, "resource_type": "worker", "action": "read", "description": "Ver trabajadores", "is_active": True},
    {"id": 37, "resource_type": "worker", "action": "update", "description": "Actualizar trabajadores", "is_active": True},
    {"id": 38, "resource_type": "worker", "action": "delete", "description": "Eliminar trabajadores", "is_active": True},
    {"id": 39, "resource_type": "reinduction", "action": "create", "description": "Crear reinducciones", "is_active": True},
    {"id": 40, "resource_type": "reinduction", "action": "read", "description": "Ver reinducciones", "is_active": True},
    {"id": 41, "resource_type": "reinduction", "action": "update", "description": "Actualizar reinducciones", "is_active": True},
    {"id": 42, "resource_type": "reinduction", "action": "delete", "description": "Eliminar reinducciones", "is_active": True},
    {"id": 43, "resource_type": "admin_config", "action": "create", "description": "Crear configuraciones administrativas", "is_active": True},
    {"id": 44, "resource_type": "admin_config", "action": "read", "description": "Ver configuraciones administrativas", "is_active": True},
    {"id": 45, "resource_type": "admin_config", "action": "update", "description": "Actualizar configuraciones administrativas", "is_active": True},
    {"id": 46, "resource_type": "admin_config", "action": "delete", "description": "Eliminar configuraciones administrativas", "is_active": True},
    {"id": 47, "resource_type": "seguimiento", "action": "create", "description": "Crear seguimientos de salud ocupacional", "is_active": True},
    {"id": 48, "resource_type": "seguimiento", "action": "read", "description": "Ver seguimientos de salud ocupacional", "is_active": True},
    {"id": 49, "resource_type": "seguimiento", "action": "update", "description": "Actualizar seguimientos de salud ocupacional", "is_active": True},
    {"id": 50, "resource_type": "seguimiento", "action": "delete", "description": "Eliminar seguimientos de salud ocupacional", "is_active": True},
    {"id": 51, "resource_type": "occupational_exam", "action": "create", "description": "Crear exámenes ocupacionales", "is_active": True},
    {"id": 52, "resource_type": "occupational_exam", "action": "read", "description": "Ver exámenes ocupacionales", "is_active": True},
    {"id": 53, "resource_type": "occupational_exam", "action": "update", "description": "Actualizar exámenes ocupacionales", "is_active": True},
    {"id": 54, "resource_type": "occupational_exam", "action": "delete", "description": "Eliminar exámenes ocupacionales", "is_active": True},
    {"id": 55, "resource_type": "progress", "action": "read", "description": "Ver progreso de usuarios", "is_active": True},
    {"id": 56, "resource_type": "progress", "action": "update", "description": "Actualizar progreso de usuarios", "is_active": True},
]

@router.get("/", response_model=List[Permission])
async def get_permissions(
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=1000),  # Aumenté el límite máximo a 1000
    is_active: Optional[bool] = Query(None, description="Filtrar por estado activo"),
    resource_type: Optional[str] = Query(None, description="Filtrar por tipo de recurso"),
    action: Optional[str] = Query(None, description="Filtrar por acción"),
    current_user: User = Depends(require_admin),
):
    """Obtener lista de permisos del sistema"""
    permissions = PERMISSIONS_DATA.copy()
    
    # Aplicar filtros
    if is_active is not None:
        permissions = [p for p in permissions if p["is_active"] == is_active]
    
    if resource_type:
        permissions = [p for p in permissions if p["resource_type"] == resource_type]
    
    if action:
        permissions = [p for p in permissions if p["action"] == action]
    
    # Aplicar paginación
    total = len(permissions)
    permissions = permissions[skip:skip + limit]
    
    return permissions

@router.get("/resources", response_model=List[str])
async def get_resource_types(
    current_user: User = Depends(require_admin),
):
    """Obtener lista de tipos de recursos disponibles"""
    resource_types = list(set(p["resource_type"] for p in PERMISSIONS_DATA))
    return sorted(resource_types)

@router.get("/actions", response_model=List[str])
async def get_actions(
    current_user: User = Depends(require_admin),
):
    """Obtener lista de acciones disponibles"""
    actions = list(set(p["action"] for p in PERMISSIONS_DATA))
    return sorted(actions)


# ============================================================================
# ENDPOINTS DE ROLES PERSONALIZADOS
# ============================================================================

@router.get("/roles/", response_model=List[CustomRoleList])
async def get_custom_roles(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    is_active: Optional[bool] = Query(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Obtener lista de roles personalizados"""
    query = db.query(CustomRole)
    
    if is_active is not None:
        query = query.filter(CustomRole.is_active == is_active)
    
    query = query.order_by(CustomRole.name)
    roles = query.offset(skip).limit(limit).all()
    
    return roles


@router.post("/roles/", response_model=CustomRoleResponse, status_code=status.HTTP_201_CREATED)
async def create_custom_role(
    role_data: CustomRoleCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Crear un nuevo rol personalizado"""
    # Verificar que el nombre no exista
    existing_role = db.query(CustomRole).filter(CustomRole.name == role_data.name).first()
    if existing_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un rol con el nombre '{role_data.name}'"
        )
    
    # Crear el rol
    new_role = CustomRole(
        name=role_data.name,
        display_name=role_data.display_name,
        description=role_data.description,
        is_active=role_data.is_active,
        is_system_role=False
    )
    
    db.add(new_role)
    db.commit()
    db.refresh(new_role)
    
    return new_role


@router.get("/roles/{role_id}", response_model=CustomRoleResponse)
async def get_custom_role(
    role_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Obtener un rol específico por ID"""
    role = db.query(CustomRole).filter(CustomRole.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rol no encontrado"
        )
    return role


@router.put("/roles/{role_id}", response_model=CustomRoleResponse)
async def update_custom_role(
    role_id: int,
    role_data: CustomRoleUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Actualizar un rol personalizado"""
    role = db.query(CustomRole).filter(CustomRole.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rol no encontrado"
        )
    
    # Verificar que no sea un rol del sistema
    if role.is_system_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pueden modificar los roles del sistema"
        )
    
    # Verificar nombre único si se está cambiando
    if role_data.name and role_data.name != role.name:
        existing_role = db.query(CustomRole).filter(
            CustomRole.name == role_data.name,
            CustomRole.id != role_id
        ).first()
        if existing_role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe un rol con el nombre '{role_data.name}'"
            )
    
    # Actualizar campos
    update_data = role_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(role, field, value)
    
    role.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(role)
    
    return role


@router.delete("/roles/{role_id}")
async def delete_custom_role(
    role_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Eliminar un rol personalizado"""
    role = db.query(CustomRole).filter(CustomRole.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rol no encontrado"
        )
    
    # Verificar que no sea un rol del sistema
    if role.is_system_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pueden eliminar los roles del sistema"
        )
    
    db.delete(role)
    db.commit()
    
    return {"message": "Rol eliminado exitosamente"}


@router.get("/roles/{role_id}/permissions/")
async def get_role_permissions(
    role_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Obtener permisos asignados a un rol"""
    role = db.query(CustomRole).filter(CustomRole.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rol no encontrado"
        )
    
    # Por ahora retornamos una lista vacía ya que no tenemos la tabla de permisos implementada
    return []


@router.delete("/roles/{role_id}/permissions/")
async def remove_all_role_permissions(
    role_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Remover todos los permisos de un rol"""
    role = db.query(CustomRole).filter(CustomRole.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rol no encontrado"
        )
    
    # Por ahora solo retornamos un mensaje ya que no tenemos la tabla de permisos implementada
    return {"message": "Permisos removidos exitosamente"}