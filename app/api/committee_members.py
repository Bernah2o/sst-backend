"""
API endpoints for Committee Members Management
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc, asc
from datetime import date

from app.database import get_db
from app.dependencies import get_current_user
from app.models.committee import (
    Committee, CommitteeMember, CommitteeRole
)
from app.models.user import User
from app.schemas.committee import (
    CommitteeMember as CommitteeMemberSchema,
    CommitteeMemberCreate,
    CommitteeMemberUpdate,
    CommitteeRole as CommitteeRoleSchema,
    CommitteeRoleCreate,
    CommitteeRoleUpdate
)

router = APIRouter()

# Committee Role endpoints
@router.get("/roles", response_model=List[CommitteeRoleSchema])
async def get_committee_roles(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener roles de comités"""
    query = db.query(CommitteeRole)
    
    if is_active is not None:
        query = query.filter(CommitteeRole.is_active == is_active)
    
    query = query.order_by(CommitteeRole.name)
    roles = query.offset(skip).limit(limit).all()
    
    return roles

@router.post("/roles", response_model=CommitteeRoleSchema, status_code=status.HTTP_201_CREATED)
async def create_committee_role(
    role: CommitteeRoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Crear un nuevo rol de comité"""
    # Verificar si ya existe un rol con el mismo nombre
    existing_role = db.query(CommitteeRole).filter(
        CommitteeRole.name == role.name
    ).first()
    
    if existing_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un rol con este nombre"
        )
    
    db_role = CommitteeRole(**role.model_dump())
    db.add(db_role)
    db.commit()
    db.refresh(db_role)
    
    return db_role

@router.get("/roles/{role_id}", response_model=CommitteeRoleSchema)
async def get_committee_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener un rol de comité por ID"""
    role = db.query(CommitteeRole).filter(CommitteeRole.id == role_id).first()
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rol no encontrado"
        )
    
    return role

@router.put("/roles/{role_id}", response_model=CommitteeRoleSchema)
async def update_committee_role(
    role_id: int,
    role_update: CommitteeRoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Actualizar un rol de comité"""
    role = db.query(CommitteeRole).filter(CommitteeRole.id == role_id).first()
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rol no encontrado"
        )
    
    # Verificar nombre único si se está actualizando
    if role_update.name and role_update.name != role.name:
        existing_role = db.query(CommitteeRole).filter(
            and_(
                CommitteeRole.name == role_update.name,
                CommitteeRole.id != role_id
            )
        ).first()
        
        if existing_role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un rol con este nombre"
            )
    
    update_data = role_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(role, field, value)
    
    db.commit()
    db.refresh(role)
    
    return role

@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_committee_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Eliminar un rol de comité"""
    role = db.query(CommitteeRole).filter(CommitteeRole.id == role_id).first()
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rol no encontrado"
        )
    
    # Verificar si hay miembros usando este rol
    members_count = db.query(CommitteeMember).filter(
        CommitteeMember.role_id == role_id
    ).count()
    
    if members_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar el rol porque hay miembros que lo usan"
        )
    
    db.delete(role)
    db.commit()

# Committee Member endpoints
@router.get("/", response_model=List[CommitteeMemberSchema])
async def get_committee_members(
    committee_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    role: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener miembros de comités con filtros"""
    query = db.query(CommitteeMember).options(
        joinedload(CommitteeMember.committee),
        joinedload(CommitteeMember.user),
        joinedload(CommitteeMember.role_rel)
    )
    
    # Filtros
    if committee_id:
        query = query.filter(CommitteeMember.committee_id == committee_id)
    
    if user_id:
        query = query.filter(CommitteeMember.user_id == user_id)
    
    if role:
        query = query.filter(CommitteeMember.role == role)
    
    if is_active is not None:
        query = query.filter(CommitteeMember.is_active == is_active)
    
    # Ordenar por fecha de inicio descendente
    query = query.order_by(desc(CommitteeMember.start_date))
    
    members = query.offset(skip).limit(limit).all()
    
    return members

@router.post("/", response_model=CommitteeMemberSchema, status_code=status.HTTP_201_CREATED)
async def create_committee_member(
    member: CommitteeMemberCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Agregar un nuevo miembro a un comité"""
    # Verificar que el comité existe
    committee = db.query(Committee).filter(Committee.id == member.committee_id).first()
    if not committee:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Comité no encontrado"
        )
    
    # Verificar que el usuario existe
    user = db.query(User).filter(User.id == member.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario no encontrado"
        )
    
    # Verificar que el rol existe
    role = db.query(CommitteeRole).filter(CommitteeRole.id == member.role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rol no encontrado"
        )
    
    # Verificar que no existe una membresía activa para este usuario en este comité
    existing_member = db.query(CommitteeMember).filter(
        and_(
            CommitteeMember.committee_id == member.committee_id,
            CommitteeMember.user_id == member.user_id,
            CommitteeMember.is_active == True
        )
    ).first()
    
    if existing_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario ya es miembro activo de este comité"
        )
    
    # Verificar límites de roles específicos (ej: solo un presidente)
    if member.role and member.role in ["PRESIDENT", "VICE_PRESIDENT", "SECRETARY"]:
        existing_role_member = db.query(CommitteeMember).filter(
            and_(
                CommitteeMember.committee_id == member.committee_id,
                CommitteeMember.role == member.role,
                CommitteeMember.is_active == True
            )
        ).first()
        
        if existing_role_member:
            role_names = {
                "PRESIDENT": "presidente",
                "VICE_PRESIDENT": "vicepresidente",
                "SECRETARY": "secretario"
            }
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe un {role_names[member.role]} activo en este comité"
            )
    
    member_data = member.model_dump()
    member_data["created_by"] = current_user.id
    
    db_member = CommitteeMember(**member_data)
    db.add(db_member)
    db.commit()
    db.refresh(db_member)
    
    return db_member

@router.get("/{member_id}", response_model=CommitteeMemberSchema)
async def get_committee_member(
    member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener un miembro de comité por ID"""
    member = db.query(CommitteeMember).options(
        joinedload(CommitteeMember.committee),
        joinedload(CommitteeMember.role_rel)
    ).filter(CommitteeMember.id == member_id).first()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Miembro no encontrado"
        )
    
    return member

@router.put("/{member_id}", response_model=CommitteeMemberSchema)
async def update_committee_member(
    member_id: int,
    member_update: CommitteeMemberUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Actualizar un miembro de comité"""
    member = db.query(CommitteeMember).filter(CommitteeMember.id == member_id).first()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Miembro no encontrado"
        )
    
    # Verificar rol si se está actualizando
    if member_update.role_id:
        role = db.query(CommitteeRole).filter(
            CommitteeRole.id == member_update.role_id
        ).first()
        
        if not role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rol no encontrado"
            )
    
    # Verificar límites de roles específicos si se está cambiando el rol
    if member_update.role and member_update.role != member.role:
        if member_update.role in ["PRESIDENT", "VICE_PRESIDENT", "SECRETARY"]:
            existing_role_member = db.query(CommitteeMember).filter(
                and_(
                    CommitteeMember.committee_id == member.committee_id,
                    CommitteeMember.role == member_update.role,
                    CommitteeMember.is_active == True,
                    CommitteeMember.id != member_id
                )
            ).first()
            
            if existing_role_member:
                role_names = {
                    "PRESIDENT": "presidente",
                    "VICE_PRESIDENT": "vicepresidente",
                    "SECRETARY": "secretario"
                }
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Ya existe un {role_names[member_update.role]} activo en este comité"
                )
    
    update_data = member_update.model_dump(exclude_unset=True)
    update_data["updated_by"] = current_user.id
    
    for field, value in update_data.items():
        setattr(member, field, value)
    
    db.commit()
    db.refresh(member)
    
    return member

@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_committee_member(
    member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Eliminar un miembro de comité"""
    member = db.query(CommitteeMember).filter(CommitteeMember.id == member_id).first()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Miembro no encontrado"
        )
    
    db.delete(member)
    db.commit()

@router.post("/{member_id}/activate", response_model=CommitteeMemberSchema)
async def activate_committee_member(
    member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Activar un miembro de comité"""
    member = db.query(CommitteeMember).filter(CommitteeMember.id == member_id).first()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Miembro no encontrado"
        )
    
    # Verificar que no existe otra membresía activa para este usuario en este comité
    existing_member = db.query(CommitteeMember).filter(
        and_(
            CommitteeMember.committee_id == member.committee_id,
            CommitteeMember.user_id == member.user_id,
            CommitteeMember.is_active == True,
            CommitteeMember.id != member_id
        )
    ).first()
    
    if existing_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario ya tiene una membresía activa en este comité"
        )
    
    member.is_active = True
    db.commit()
    db.refresh(member)
    
    return member

@router.post("/{member_id}/deactivate", response_model=CommitteeMemberSchema)
async def deactivate_committee_member(
    member_id: int,
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Desactivar un miembro de comité"""
    member = db.query(CommitteeMember).filter(CommitteeMember.id == member_id).first()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Miembro no encontrado"
        )
    
    member.is_active = False
    if end_date:
        member.end_date = end_date
    elif not member.end_date:
        member.end_date = date.today()
    
    db.commit()
    db.refresh(member)
    
    return member

@router.get("/committee/{committee_id}", response_model=List[CommitteeMemberSchema])
async def get_members_by_committee(
    committee_id: int,
    is_active: Optional[bool] = Query(None),
    role: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener todos los miembros de un comité específico"""
    # Verificar que el comité existe
    committee = db.query(Committee).filter(Committee.id == committee_id).first()
    if not committee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comité no encontrado"
        )
    
    query = db.query(CommitteeMember).options(
        joinedload(CommitteeMember.role_rel)
    ).filter(CommitteeMember.committee_id == committee_id)
    
    if is_active is not None:
        query = query.filter(CommitteeMember.is_active == is_active)
    
    if role:
        query = query.filter(CommitteeMember.role == role)
    
    query = query.order_by(CommitteeMember.role, CommitteeMember.start_date)
    
    members = query.all()
    
    return members

@router.get("/user/{user_id}", response_model=List[CommitteeMemberSchema])
async def get_memberships_by_user(
    user_id: int,
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener todas las membresías de un usuario específico"""
    # Verificar que el usuario existe
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    query = db.query(CommitteeMember).options(
        joinedload(CommitteeMember.committee),
        joinedload(CommitteeMember.role_rel)
    ).filter(CommitteeMember.user_id == user_id)
    
    if is_active is not None:
        query = query.filter(CommitteeMember.is_active == is_active)
    
    query = query.order_by(desc(CommitteeMember.start_date))
    
    memberships = query.all()
    
    return memberships