from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import require_admin, get_current_active_user
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

# Lista de permisos disponibles en el sistema basados en páginas/módulos
PERMISSIONS_DATA = [
    # Dashboard
    {"id": 1, "resource_type": "dashboard", "action": "view", "description": "Acceder al dashboard principal", "is_active": True},
    
    # Gestión de Usuarios
    {"id": 2, "resource_type": "users", "action": "view", "description": "Acceder a la página de usuarios", "is_active": True},
    {"id": 3, "resource_type": "users", "action": "create", "description": "Crear usuarios", "is_active": True},
    {"id": 4, "resource_type": "users", "action": "read", "description": "Ver detalles de usuarios", "is_active": True},
    {"id": 5, "resource_type": "users", "action": "update", "description": "Editar usuarios", "is_active": True},
    {"id": 6, "resource_type": "users", "action": "delete", "description": "Eliminar usuarios", "is_active": True},
    
    # Gestión de Cursos
    {"id": 7, "resource_type": "courses", "action": "view", "description": "Acceder a la página de cursos", "is_active": True},
    {"id": 8, "resource_type": "courses", "action": "create", "description": "Crear cursos", "is_active": True},
    {"id": 9, "resource_type": "courses", "action": "read", "description": "Ver detalles de cursos", "is_active": True},
    {"id": 10, "resource_type": "courses", "action": "update", "description": "Editar cursos", "is_active": True},
    {"id": 11, "resource_type": "courses", "action": "delete", "description": "Eliminar cursos", "is_active": True},
    {"id": 12, "resource_type": "courses", "action": "enroll", "description": "Inscribirse en cursos", "is_active": True},
    
    # Gestión de Módulos de Cursos
    {"id": 77, "resource_type": "modules", "action": "view", "description": "Acceder a la página de módulos", "is_active": True},
    {"id": 78, "resource_type": "modules", "action": "create", "description": "Crear módulos", "is_active": True},
    {"id": 79, "resource_type": "modules", "action": "read", "description": "Ver detalles de módulos", "is_active": True},
    {"id": 80, "resource_type": "modules", "action": "update", "description": "Editar módulos", "is_active": True},
    {"id": 81, "resource_type": "modules", "action": "delete", "description": "Eliminar módulos", "is_active": True},
    
    # Gestión de Materiales de Cursos
    {"id": 82, "resource_type": "materials", "action": "view", "description": "Acceder a la página de materiales", "is_active": True},
    {"id": 83, "resource_type": "materials", "action": "create", "description": "Crear materiales", "is_active": True},
    {"id": 84, "resource_type": "materials", "action": "read", "description": "Ver detalles de materiales", "is_active": True},
    {"id": 85, "resource_type": "materials", "action": "update", "description": "Editar materiales", "is_active": True},
    {"id": 86, "resource_type": "materials", "action": "delete", "description": "Eliminar materiales", "is_active": True},
    
    # Gestión de Evaluaciones
    {"id": 13, "resource_type": "evaluations", "action": "view", "description": "Acceder a la página de evaluaciones", "is_active": True},
    {"id": 14, "resource_type": "evaluations", "action": "create", "description": "Crear evaluaciones", "is_active": True},
    {"id": 15, "resource_type": "evaluations", "action": "read", "description": "Ver detalles de evaluaciones", "is_active": True},
    {"id": 16, "resource_type": "evaluations", "action": "update", "description": "Editar evaluaciones", "is_active": True},
    {"id": 17, "resource_type": "evaluations", "action": "delete", "description": "Eliminar evaluaciones", "is_active": True},
    {"id": 18, "resource_type": "evaluations", "action": "submit", "description": "Responder evaluaciones", "is_active": True},
    
    # Gestión de Encuestas
    {"id": 19, "resource_type": "surveys", "action": "view", "description": "Acceder a la página de encuestas", "is_active": True},
    {"id": 20, "resource_type": "surveys", "action": "create", "description": "Crear encuestas", "is_active": True},
    {"id": 21, "resource_type": "surveys", "action": "read", "description": "Ver detalles de encuestas", "is_active": True},
    {"id": 22, "resource_type": "surveys", "action": "update", "description": "Editar encuestas", "is_active": True},
    {"id": 23, "resource_type": "surveys", "action": "delete", "description": "Eliminar encuestas", "is_active": True},
    {"id": 24, "resource_type": "surveys", "action": "submit", "description": "Responder encuestas", "is_active": True},
    
    # Gestión de Certificados
    {"id": 25, "resource_type": "certificates", "action": "view", "description": "Acceder a la página de certificados", "is_active": True},
    {"id": 26, "resource_type": "certificates", "action": "create", "description": "Generar certificados", "is_active": True},
    {"id": 27, "resource_type": "certificates", "action": "read", "description": "Ver certificados", "is_active": True},
    {"id": 28, "resource_type": "certificates", "action": "update", "description": "Editar certificados", "is_active": True},
    {"id": 29, "resource_type": "certificates", "action": "delete", "description": "Eliminar certificados", "is_active": True},
    {"id": 30, "resource_type": "certificates", "action": "download", "description": "Descargar certificados", "is_active": True},
    
    # Gestión de Asistencia
    {"id": 31, "resource_type": "attendance", "action": "view", "description": "Acceder a la página de asistencia", "is_active": True},
    {"id": 32, "resource_type": "attendance", "action": "create", "description": "Registrar asistencia", "is_active": True},
    {"id": 33, "resource_type": "attendance", "action": "read", "description": "Ver registros de asistencia", "is_active": True},
    {"id": 34, "resource_type": "attendance", "action": "update", "description": "Editar asistencia", "is_active": True},
    {"id": 35, "resource_type": "attendance", "action": "delete", "description": "Eliminar registros de asistencia", "is_active": True},
    
    # Reportes
    {"id": 36, "resource_type": "reports", "action": "view", "description": "Acceder a la página de reportes", "is_active": True},
    {"id": 37, "resource_type": "reports", "action": "create", "description": "Generar reportes", "is_active": True},
    {"id": 38, "resource_type": "reports", "action": "read", "description": "Ver reportes", "is_active": True},
    {"id": 39, "resource_type": "reports", "action": "export", "description": "Exportar reportes", "is_active": True},
    
    # Notificaciones
    {"id": 40, "resource_type": "notifications", "action": "view", "description": "Acceder a la página de notificaciones", "is_active": True},
    {"id": 41, "resource_type": "notifications", "action": "create", "description": "Crear notificaciones", "is_active": True},
    {"id": 42, "resource_type": "notifications", "action": "read", "description": "Ver notificaciones", "is_active": True},
    {"id": 43, "resource_type": "notifications", "action": "update", "description": "Editar notificaciones", "is_active": True},
    {"id": 44, "resource_type": "notifications", "action": "delete", "description": "Eliminar notificaciones", "is_active": True},
    
    # Gestión de Trabajadores
    {"id": 45, "resource_type": "workers", "action": "view", "description": "Acceder a la página de trabajadores", "is_active": True},
    {"id": 46, "resource_type": "workers", "action": "create", "description": "Crear trabajadores", "is_active": True},
    {"id": 47, "resource_type": "workers", "action": "read", "description": "Ver detalles de trabajadores", "is_active": True},
    {"id": 48, "resource_type": "workers", "action": "update", "description": "Editar trabajadores", "is_active": True},
    {"id": 49, "resource_type": "workers", "action": "delete", "description": "Eliminar trabajadores", "is_active": True},
    
    # Reinducciones
    {"id": 50, "resource_type": "reinductions", "action": "view", "description": "Acceder a la página de reinducciones", "is_active": True},
    {"id": 51, "resource_type": "reinductions", "action": "create", "description": "Crear reinducciones", "is_active": True},
    {"id": 52, "resource_type": "reinductions", "action": "read", "description": "Ver reinducciones", "is_active": True},
    {"id": 53, "resource_type": "reinductions", "action": "update", "description": "Editar reinducciones", "is_active": True},
    {"id": 54, "resource_type": "reinductions", "action": "delete", "description": "Eliminar reinducciones", "is_active": True},
    
    # Configuración Administrativa
    {"id": 55, "resource_type": "admin_config", "action": "view", "description": "Acceder a configuración administrativa", "is_active": True},
    {"id": 56, "resource_type": "admin_config", "action": "create", "description": "Crear configuraciones", "is_active": True},
    {"id": 57, "resource_type": "admin_config", "action": "read", "description": "Ver configuraciones", "is_active": True},
    {"id": 58, "resource_type": "admin_config", "action": "update", "description": "Editar configuraciones", "is_active": True},
    {"id": 59, "resource_type": "admin_config", "action": "delete", "description": "Eliminar configuraciones", "is_active": True},
    
    # Seguimiento de Salud Ocupacional
    {"id": 60, "resource_type": "health_tracking", "action": "view", "description": "Acceder a seguimiento de salud ocupacional", "is_active": True},
    {"id": 61, "resource_type": "health_tracking", "action": "create", "description": "Crear seguimientos", "is_active": True},
    {"id": 62, "resource_type": "health_tracking", "action": "read", "description": "Ver seguimientos", "is_active": True},
    {"id": 63, "resource_type": "health_tracking", "action": "update", "description": "Editar seguimientos", "is_active": True},
    {"id": 64, "resource_type": "health_tracking", "action": "delete", "description": "Eliminar seguimientos", "is_active": True},
    
    # Gestión de Roles
    {"id": 65, "resource_type": "roles", "action": "view", "description": "Acceder a gestión de roles", "is_active": True},
    {"id": 66, "resource_type": "roles", "action": "create", "description": "Crear roles", "is_active": True},
    {"id": 67, "resource_type": "roles", "action": "read", "description": "Ver roles", "is_active": True},
    {"id": 68, "resource_type": "roles", "action": "update", "description": "Editar roles", "is_active": True},
    {"id": 69, "resource_type": "roles", "action": "delete", "description": "Eliminar roles", "is_active": True},
    {"id": 70, "resource_type": "roles", "action": "assign_permissions", "description": "Asignar permisos a roles", "is_active": True},
    
    # Archivos
    {"id": 71, "resource_type": "files", "action": "view", "description": "Acceder a gestión de archivos", "is_active": True},
    {"id": 72, "resource_type": "files", "action": "create", "description": "Subir archivos", "is_active": True},
    {"id": 73, "resource_type": "files", "action": "read", "description": "Ver archivos", "is_active": True},
    {"id": 74, "resource_type": "files", "action": "update", "description": "Editar archivos", "is_active": True},
    {"id": 75, "resource_type": "files", "action": "delete", "description": "Eliminar archivos", "is_active": True},
    {"id": 76, "resource_type": "files", "action": "download", "description": "Descargar archivos", "is_active": True},
    {"id": 87, "resource_type": "seguimiento", "action": "update", "description": "Actualizar seguimientos de salud ocupacional", "is_active": True},
    {"id": 88, "resource_type": "seguimiento", "action": "delete", "description": "Eliminar seguimientos de salud ocupacional", "is_active": True},
    {"id": 89, "resource_type": "occupational_exam", "action": "create", "description": "Crear exámenes ocupacionales", "is_active": True},
    {"id": 90, "resource_type": "occupational_exam", "action": "read", "description": "Ver exámenes ocupacionales", "is_active": True},
    {"id": 91, "resource_type": "occupational_exam", "action": "update", "description": "Actualizar exámenes ocupacionales", "is_active": True},
    {"id": 92, "resource_type": "occupational_exam", "action": "delete", "description": "Eliminar exámenes ocupacionales", "is_active": True},
    {"id": 93, "resource_type": "progress", "action": "read", "description": "Ver progreso de usuarios", "is_active": True},
    {"id": 94, "resource_type": "progress", "action": "update", "description": "Actualizar progreso de usuarios", "is_active": True},
    
    # Gestión de Proveedores
    {"id": 95, "resource_type": "suppliers", "action": "view", "description": "Acceder a la página de proveedores", "is_active": True},
    {"id": 96, "resource_type": "suppliers", "action": "create", "description": "Crear proveedores", "is_active": True},
    {"id": 97, "resource_type": "suppliers", "action": "read", "description": "Ver detalles de proveedores", "is_active": True},
    {"id": 98, "resource_type": "suppliers", "action": "update", "description": "Editar proveedores", "is_active": True},
    {"id": 99, "resource_type": "suppliers", "action": "delete", "description": "Eliminar proveedores", "is_active": True},
    
    # Gestión de Ausentismo
    {"id": 100, "resource_type": "absenteeism", "action": "view", "description": "Acceder a la página de ausentismo", "is_active": True},
    {"id": 101, "resource_type": "absenteeism", "action": "create", "description": "Crear registros de ausentismo", "is_active": True},
    {"id": 102, "resource_type": "absenteeism", "action": "read", "description": "Ver detalles de ausentismo", "is_active": True},
    {"id": 103, "resource_type": "absenteeism", "action": "update", "description": "Editar registros de ausentismo", "is_active": True},
    {"id": 104, "resource_type": "absenteeism", "action": "delete", "description": "Eliminar registros de ausentismo", "is_active": True},
    
    # Seguimiento (adicional para compatibilidad)
    {"id": 105, "resource_type": "seguimiento", "action": "view", "description": "Acceder a seguimientos de salud ocupacional", "is_active": True},
    {"id": 106, "resource_type": "seguimiento", "action": "create", "description": "Crear seguimientos de salud ocupacional", "is_active": True},
    {"id": 107, "resource_type": "seguimiento", "action": "read", "description": "Ver seguimientos de salud ocupacional", "is_active": True},
    
    # Exámenes ocupacionales (adicional para vista)
    {"id": 108, "resource_type": "occupational_exam", "action": "view", "description": "Acceder a exámenes ocupacionales", "is_active": True},
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
    current_user: User = Depends(get_current_active_user),
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
    
    # Obtener los permission_ids asociados al rol desde la tabla role_permissions
    from app.models.custom_role import role_permissions
    permission_ids_result = db.execute(
        role_permissions.select().where(role_permissions.c.role_id == role_id)
    ).fetchall()
    
    permission_ids = [row.permission_id for row in permission_ids_result]
    
    # Filtrar los permisos de PERMISSIONS_DATA que están asignados al rol
    assigned_permissions = [
        permission for permission in PERMISSIONS_DATA 
        if permission["id"] in permission_ids
    ]
    
    return assigned_permissions


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
    
    # Eliminar todos los permisos del rol desde la tabla role_permissions
    from app.models.custom_role import role_permissions
    db.execute(
        role_permissions.delete().where(role_permissions.c.role_id == role_id)
    )
    db.commit()
    
    return {"message": "Permisos removidos exitosamente"}


@router.post("/check")
async def check_permission(
    permission_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Verificar si el usuario actual tiene un permiso específico"""
    resource_type = permission_data.get("resource_type")
    action = permission_data.get("action")
    
    if not resource_type or not action:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requieren 'resource_type' y 'action'"
        )
    
    # Usar la lógica de PermissionChecker para verificar el permiso
    from app.dependencies import PermissionChecker
    checker = PermissionChecker(resource_type, action)
    
    try:
        has_permission = checker._has_permission(current_user, resource_type, action)
        return {"has_permission": has_permission}
    except Exception as e:
        # En caso de error, denegar el permiso por seguridad
        return {"has_permission": False}


@router.post("/check-batch")
async def check_permissions_batch(
    permissions_data: List[dict],
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Verificar múltiples permisos en una sola llamada para optimizar rendimiento"""
    if not permissions_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere al menos un permiso para verificar"
        )
    
    # Validar que todos los elementos tengan resource_type y action
    for perm in permissions_data:
        if not perm.get("resource_type") or not perm.get("action"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cada permiso debe tener 'resource_type' y 'action'"
            )
    
    # Usar la lógica de PermissionChecker para verificar cada permiso
    from app.dependencies import PermissionChecker
    
    results = []
    for perm in permissions_data:
        try:
            checker = PermissionChecker(perm["resource_type"], perm["action"])
            has_permission = checker._has_permission(current_user, perm["resource_type"], perm["action"])
            results.append({
                "resource_type": perm["resource_type"],
                "action": perm["action"],
                "has_permission": has_permission
            })
        except Exception as e:
            # En caso de error, denegar el permiso por seguridad
            results.append({
                "resource_type": perm["resource_type"],
                "action": perm["action"],
                "has_permission": False
            })
    
    return {"permissions": results}


@router.get("/my-pages")
async def get_my_pages(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get pages accessible by current user based on their custom role
    """
    # If user is ADMIN, return all pages
    if current_user.role == UserRole.ADMIN:
        # Return all available page permissions
        pages = []
        for perm in PERMISSIONS_DATA:
            if perm["action"] == "view":
                pages.append({
                    "resource_type": perm["resource_type"],
                    "action": perm["action"],
                    "has_permission": True
                })
        return {"pages": pages}
    
    # For users with custom roles, check their specific permissions
    if not current_user.custom_role_id:
        return {"pages": []}
    
    pages = []
    
    # Check view permissions for all resources
    for perm in PERMISSIONS_DATA:
        if perm["action"] == "view":
            has_permission = _check_user_permission(current_user, perm["resource_type"], "view", db)
            pages.append({
                "resource_type": perm["resource_type"],
                "action": perm["action"],
                "has_permission": has_permission
            })
    
    return {"pages": pages}


def _check_user_permission(user: User, resource_type: str, action: str, db: Session) -> bool:
    """
    Helper function to check if user has permission for specific resource and action
    """
    # Admin has all permissions
    if user.role == UserRole.ADMIN:
        return True
    
    # Check custom role permissions
    if user.custom_role_id:
        return _check_custom_role_permission(user, resource_type, action, db)
    
    # Fallback to hardcoded role permissions
    return _check_hardcoded_role_permission(user, resource_type, action)


def _check_custom_role_permission(user: User, resource_type: str, action: str, db: Session) -> bool:
    """
    Check permission based on custom role
    """
    try:
        from app.models.custom_role import role_permissions
        
        # Get permission IDs for this custom role
        permission_ids_result = db.execute(
            role_permissions.select().where(role_permissions.c.role_id == user.custom_role_id)
        ).fetchall()
        
        permission_ids = [row.permission_id for row in permission_ids_result]
        
        # Check if the required permission exists
        required_permission = next(
            (p for p in PERMISSIONS_DATA 
             if p["resource_type"] == resource_type and p["action"] == action),
            None
        )
        
        if required_permission and required_permission["id"] in permission_ids:
            return True
            
        return False
    except Exception as e:
        # If there's any error with custom role checking, return False
        print(f"Error checking custom role permission: {e}")
        return False


def _check_hardcoded_role_permission(user: User, resource_type: str, action: str) -> bool:
    """
    Check permission based on hardcoded role matrix
    """
    # Basic permissions for hardcoded roles
    permissions = {
        UserRole.TRAINER: {
            "courses": ["view", "read"],
            "evaluations": ["view", "read"],
            "attendance": ["view", "read"],
            "certificates": ["view", "read"]
        },
        UserRole.EMPLOYEE: {
            "courses": ["view", "read"],
            "evaluations": ["view", "read", "submit"],
            "surveys": ["view", "read", "submit"],
            "certificates": ["view", "read", "download"]
        },
        UserRole.SUPERVISOR: {
            "courses": ["view", "read"],
            "evaluations": ["view", "read"],
            "attendance": ["view", "read"],
            "reports": ["view", "read"],
            "workers": ["view", "read"]
        }
    }
    
    user_permissions = permissions.get(user.role, {})
    resource_actions = user_permissions.get(resource_type, [])
    
    return action in resource_actions

@router.post("/roles/{role_id}/bulk-assign-permissions")
async def bulk_assign_permissions(
    role_id: int,
    assignment_data: RolePermissionAssignment,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Asignar permisos masivamente a un rol"""
    # Verificar que el rol existe
    role = db.query(CustomRole).filter(CustomRole.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rol no encontrado"
        )
    
    # Verificar que todos los permission_ids son válidos
    valid_permission_ids = [p["id"] for p in PERMISSIONS_DATA]
    invalid_permissions = [
        pid for pid in assignment_data.permission_ids 
        if pid not in valid_permission_ids
    ]
    
    if invalid_permissions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"IDs de permisos inválidos: {invalid_permissions}"
        )
    
    # Eliminar permisos existentes del rol
    from app.models.custom_role import role_permissions
    db.execute(
        role_permissions.delete().where(role_permissions.c.role_id == role_id)
    )
    
    # Insertar los nuevos permisos
    if assignment_data.permission_ids:
        permission_assignments = [
            {"role_id": role_id, "permission_id": pid}
            for pid in assignment_data.permission_ids
        ]
        db.execute(role_permissions.insert(), permission_assignments)
    
    db.commit()
    
    return {
        "message": f"Se asignaron {len(assignment_data.permission_ids)} permisos al rol '{role.display_name}' exitosamente"
    }