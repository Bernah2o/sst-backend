"""
API endpoints for committee permissions management
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.database import get_db
from app.models.committee import CommitteePermission, Committee
from app.models.user import User
from app.schemas.committee import (
    CommitteePermission as CommitteePermissionSchema,
    CommitteePermissionCreate,
    CommitteePermissionUpdate
)
from app.dependencies import get_current_user

router = APIRouter()

@router.get("/accessible-committees")
async def get_user_accessible_committees(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtiene los comités a los que el usuario actual tiene acceso
    """
    try:
        # Obtener todos los comités activos
        all_committees = db.query(Committee).filter(Committee.is_active == True).all()
        
        committees_dict = {}
        
        for committee in all_committees:
            # Si el usuario es administrador, dar permisos completos
            if current_user.is_admin():
                permission_types = ["view", "edit", "manage_members", "delete"]
            else:
                # Buscar permisos específicos del usuario para este comité
                user_permissions = db.query(CommitteePermission.permission_type).filter(
                    and_(
                        CommitteePermission.committee_id == committee.id,
                        CommitteePermission.user_id == current_user.id,
                        CommitteePermission.is_active == True
                    )
                ).all()
                
                # Extraer los tipos de permisos
                permission_types = [perm[0] for perm in user_permissions]
                
                # Si no tiene permisos específicos, dar acceso básico de visualización
                if not permission_types:
                    permission_types = ["view"]
            
            committees_dict[committee.id] = {
                "committee_id": committee.id,
                "committee_name": committee.name,
                "permissions": permission_types
            }
        
        return list(committees_dict.values())
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener comités accesibles: {str(e)}")

@router.get("/check-current")
async def check_current_user_permission(
    committee_id: int = Query(..., description="ID del comité"),
    permission: str = Query(..., description="Tipo de permiso a verificar"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verifica si el usuario actual tiene un permiso específico en un comité
    """
    try:
        # Si el usuario es administrador, siempre tiene todos los permisos
        if current_user.is_admin():
            has_permission = True
        else:
            # Buscar el permiso específico del usuario
            user_permission = db.query(CommitteePermission).filter(
                and_(
                    CommitteePermission.committee_id == committee_id,
                    CommitteePermission.user_id == current_user.id,
                    CommitteePermission.permission_type == permission,
                    CommitteePermission.is_active == True
                )
            ).first()
            
            has_permission = user_permission is not None
        
        return {"has_permission": has_permission}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al verificar permisos: {str(e)}")

@router.get("/")
async def get_committee_permissions(
    committee_id: Optional[int] = Query(None, description="ID del comité"),
    user_id: Optional[int] = Query(None, description="ID del usuario"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtiene permisos de comité filtrados por comité o usuario
    """
    try:
        query = db.query(CommitteePermission)
        
        if committee_id:
            query = query.filter(CommitteePermission.committee_id == committee_id)
        
        if user_id:
            query = query.filter(CommitteePermission.user_id == user_id)
        
        permissions = query.all()
        return permissions
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener permisos: {str(e)}")

@router.get("/{permission_id}")
async def get_permission(
    permission_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtiene un permiso específico por ID
    """
    try:
        permission = db.query(CommitteePermission).filter(
            CommitteePermission.id == permission_id
        ).first()
        
        if not permission:
            raise HTTPException(status_code=404, detail="Permiso no encontrado")
        
        return permission
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener permiso: {str(e)}")

@router.post("/", response_model=CommitteePermissionSchema)
async def create_permission(
    permission_data: CommitteePermissionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Crea un nuevo permiso de comité
    """
    try:
        # Verificar que el comité existe
        committee = db.query(Committee).filter(Committee.id == permission_data.committee_id).first()
        if not committee:
            raise HTTPException(status_code=404, detail="Comité no encontrado")
        
        # Verificar que el usuario existe
        user = db.query(User).filter(User.id == permission_data.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Crear el permiso
        permission = CommitteePermission(
            committee_id=permission_data.committee_id,
            user_id=permission_data.user_id,
            permission_type=permission_data.permission_type,
            granted_by=current_user.id,
            expires_at=permission_data.expires_at,
            is_active=permission_data.is_active,
            notes=permission_data.notes
        )
        
        db.add(permission)
        db.commit()
        db.refresh(permission)
        
        return permission
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al crear permiso: {str(e)}")

@router.put("/{permission_id}", response_model=CommitteePermissionSchema)
async def update_permission(
    permission_id: int,
    permission_data: CommitteePermissionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Actualiza un permiso de comité existente
    """
    try:
        permission = db.query(CommitteePermission).filter(
            CommitteePermission.id == permission_id
        ).first()
        
        if not permission:
            raise HTTPException(status_code=404, detail="Permiso no encontrado")
        
        # Actualizar campos
        update_data = permission_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(permission, field, value)
        
        db.commit()
        db.refresh(permission)
        
        return permission
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al actualizar permiso: {str(e)}")

@router.delete("/{permission_id}")
async def delete_permission(
    permission_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Elimina un permiso de comité
    """
    try:
        permission = db.query(CommitteePermission).filter(
            CommitteePermission.id == permission_id
        ).first()
        
        if not permission:
            raise HTTPException(status_code=404, detail="Permiso no encontrado")
        
        db.delete(permission)
        db.commit()
        
        return {"message": "Permiso eliminado exitosamente"}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al eliminar permiso: {str(e)}")

@router.get("/check")
async def check_user_permission(
    committee_id: int = Query(..., description="ID del comité"),
    user_id: int = Query(..., description="ID del usuario"),
    permission: str = Query(..., description="Tipo de permiso a verificar"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verifica si un usuario específico tiene un permiso en un comité
    """
    try:
        user_permission = db.query(CommitteePermission).filter(
            and_(
                CommitteePermission.committee_id == committee_id,
                CommitteePermission.user_id == user_id,
                CommitteePermission.permission_type == permission,
                CommitteePermission.is_active == True
            )
        ).first()
        
        has_permission = user_permission is not None
        
        return {"has_permission": has_permission}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al verificar permisos: {str(e)}")