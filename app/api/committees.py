"""
API endpoints for Committee Management
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc, asc

from app.database import get_db
from app.dependencies import get_current_user
from app.models.committee import (
    Committee, CommitteeType, CommitteeMember, CommitteeMeeting,
    CommitteeActivity, CommitteeDocument, CommitteeVoting
)
from app.models.user import User
from app.schemas.committee import (
    Committee as CommitteeSchema,
    CommitteeCreate,
    CommitteeUpdate,
    CommitteeDetailed,
    CommitteeListResponse,
    CommitteeType as CommitteeTypeSchema,
    CommitteeTypeCreate,
    CommitteeTypeUpdate
)

router = APIRouter()

# Committee Type endpoints
@router.get("/types", response_model=List[CommitteeTypeSchema])
async def get_committee_types(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None, description="Buscar por nombre del tipo de comité"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener tipos de comités"""
    query = db.query(CommitteeType)

    if is_active is not None:
        query = query.filter(CommitteeType.is_active == is_active)

    if search:
        query = query.filter(CommitteeType.name.ilike(f"%{search}%"))

    query = query.order_by(CommitteeType.name)
    committee_types = query.offset(skip).limit(limit).all()

    return committee_types

@router.post("/types", response_model=CommitteeTypeSchema, status_code=status.HTTP_201_CREATED)
async def create_committee_type(
    committee_type: CommitteeTypeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Crear un nuevo tipo de comité"""
    # Verificar si ya existe un tipo con el mismo nombre
    existing_type = db.query(CommitteeType).filter(
        CommitteeType.name == committee_type.name
    ).first()
    
    if existing_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un tipo de comité con este nombre"
        )
    
    db_committee_type = CommitteeType(**committee_type.model_dump())
    db.add(db_committee_type)
    db.commit()
    db.refresh(db_committee_type)
    
    return db_committee_type

@router.get("/types/{type_id}", response_model=CommitteeTypeSchema)
async def get_committee_type(
    type_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener un tipo de comité por ID"""
    committee_type = db.query(CommitteeType).filter(CommitteeType.id == type_id).first()
    
    if not committee_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tipo de comité no encontrado"
        )
    
    return committee_type

@router.put("/types/{type_id}", response_model=CommitteeTypeSchema)
async def update_committee_type(
    type_id: int,
    committee_type_update: CommitteeTypeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Actualizar un tipo de comité"""
    committee_type = db.query(CommitteeType).filter(CommitteeType.id == type_id).first()
    
    if not committee_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tipo de comité no encontrado"
        )
    
    # Verificar nombre único si se está actualizando
    if committee_type_update.name and committee_type_update.name != committee_type.name:
        existing_type = db.query(CommitteeType).filter(
            and_(
                CommitteeType.name == committee_type_update.name,
                CommitteeType.id != type_id
            )
        ).first()
        
        if existing_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un tipo de comité con este nombre"
            )
    
    update_data = committee_type_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(committee_type, field, value)
    
    db.commit()
    db.refresh(committee_type)
    
    return committee_type

@router.delete("/types/{type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_committee_type(
    type_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Eliminar un tipo de comité"""
    committee_type = db.query(CommitteeType).filter(CommitteeType.id == type_id).first()
    
    if not committee_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tipo de comité no encontrado"
        )
    
    # Verificar si hay comités usando este tipo
    committees_count = db.query(Committee).filter(
        Committee.committee_type_id == type_id
    ).count()
    
    if committees_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar el tipo de comité porque hay comités que lo usan"
        )
    
    db.delete(committee_type)
    db.commit()

# Committee endpoints
@router.get("/", response_model=CommitteeListResponse)
@router.get("", response_model=CommitteeListResponse)  # Add route without trailing slash to avoid 307 redirect
async def get_committees(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    is_active: Optional[bool] = Query(None),
    committee_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("name", regex="^(name|created_at|establishment_date)$"),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener lista de comités con filtros y paginación"""
    query = db.query(Committee).options(
        joinedload(Committee.committee_type_rel),
        joinedload(Committee.members),
        joinedload(Committee.meetings)
    )
    
    # Filtros
    if is_active is not None:
        query = query.filter(Committee.is_active == is_active)
    
    if committee_type:
        query = query.filter(Committee.committee_type == committee_type)
    
    if search:
        search_filter = or_(
            Committee.name.ilike(f"%{search}%"),
            Committee.description.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)
    
    # Ordenamiento
    order_column = getattr(Committee, sort_by)
    if sort_order == "desc":
        query = query.order_by(desc(order_column))
    else:
        query = query.order_by(asc(order_column))
    
    # Contar total
    total = query.count()
    
    # Paginación
    committees = query.offset(skip).limit(limit).all()
    
    # Calcular páginas
    pages = (total + limit - 1) // limit
    
    return CommitteeListResponse(
        items=committees,
        total=total,
        page=(skip // limit) + 1,
        size=limit,
        pages=pages
    )

@router.post("/", response_model=CommitteeSchema, status_code=status.HTTP_201_CREATED)
@router.post("", response_model=CommitteeSchema, status_code=status.HTTP_201_CREATED)  # Add route without trailing slash to avoid 405 error
async def create_committee(
    committee: CommitteeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Crear un nuevo comité"""
    # Verificar que el tipo de comité existe
    committee_type = db.query(CommitteeType).filter(
        CommitteeType.id == committee.committee_type_id
    ).first()
    
    if not committee_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipo de comité no encontrado"
        )
    
    # Verificar nombre único
    existing_committee = db.query(Committee).filter(
        Committee.name == committee.name
    ).first()
    
    if existing_committee:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un comité con este nombre"
        )
    
    committee_data = committee.model_dump()
    committee_data["created_by"] = current_user.id
    
    db_committee = Committee(**committee_data)
    db.add(db_committee)
    db.commit()
    db.refresh(db_committee)
    
    return db_committee

@router.get("/{committee_id}", response_model=CommitteeDetailed)
async def get_committee(
    committee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener un comité por ID con detalles completos"""
    committee = db.query(Committee).options(
        joinedload(Committee.committee_type_rel),
        joinedload(Committee.members),
        joinedload(Committee.meetings),
        joinedload(Committee.activities),
        joinedload(Committee.documents),
        joinedload(Committee.votings)
    ).filter(Committee.id == committee_id).first()
    
    if not committee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comité no encontrado"
        )
    
    return committee

@router.put("/{committee_id}", response_model=CommitteeSchema)
async def update_committee(
    committee_id: int,
    committee_update: CommitteeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Actualizar un comité"""
    committee = db.query(Committee).filter(Committee.id == committee_id).first()
    
    if not committee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comité no encontrado"
        )
    
    # Verificar nombre único si se está actualizando
    if committee_update.name and committee_update.name != committee.name:
        existing_committee = db.query(Committee).filter(
            and_(
                Committee.name == committee_update.name,
                Committee.id != committee_id
            )
        ).first()
        
        if existing_committee:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un comité con este nombre"
            )
    
    # Verificar tipo de comité si se está actualizando
    if committee_update.committee_type_id:
        committee_type = db.query(CommitteeType).filter(
            CommitteeType.id == committee_update.committee_type_id
        ).first()
        
        if not committee_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tipo de comité no encontrado"
            )
    
    update_data = committee_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(committee, field, value)
    
    db.commit()
    db.refresh(committee)
    
    return committee

@router.delete("/{committee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_committee(
    committee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Eliminar un comité"""
    committee = db.query(Committee).filter(Committee.id == committee_id).first()
    
    if not committee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comité no encontrado"
        )
    
    # Verificar si hay datos relacionados
    members_count = db.query(CommitteeMember).filter(
        CommitteeMember.committee_id == committee_id
    ).count()
    
    meetings_count = db.query(CommitteeMeeting).filter(
        CommitteeMeeting.committee_id == committee_id
    ).count()
    
    if members_count > 0 or meetings_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar el comité porque tiene miembros o reuniones asociadas"
        )
    
    db.delete(committee)
    db.commit()

@router.post("/{committee_id}/activate", response_model=CommitteeSchema)
async def activate_committee(
    committee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Activar un comité"""
    committee = db.query(Committee).filter(Committee.id == committee_id).first()
    
    if not committee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comité no encontrado"
        )
    
    committee.is_active = True
    db.commit()
    db.refresh(committee)
    
    return committee

@router.post("/{committee_id}/deactivate", response_model=CommitteeSchema)
async def deactivate_committee(
    committee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Desactivar un comité"""
    committee = db.query(Committee).filter(Committee.id == committee_id).first()
    
    if not committee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comité no encontrado"
        )
    
    committee.is_active = False
    db.commit()
    db.refresh(committee)
    
    return committee

@router.get("/{committee_id}/stats")
async def get_committee_stats(
    committee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener estadísticas de un comité"""
    committee = db.query(Committee).filter(Committee.id == committee_id).first()
    
    if not committee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comité no encontrado"
        )
    
    # Contar elementos relacionados
    members_count = db.query(CommitteeMember).filter(
        and_(
            CommitteeMember.committee_id == committee_id,
            CommitteeMember.is_active == True
        )
    ).count()
    
    meetings_count = db.query(CommitteeMeeting).filter(
        CommitteeMeeting.committee_id == committee_id
    ).count()
    
    activities_count = db.query(CommitteeActivity).filter(
        CommitteeActivity.committee_id == committee_id
    ).count()
    
    documents_count = db.query(CommitteeDocument).filter(
        CommitteeDocument.committee_id == committee_id
    ).count()
    
    votings_count = db.query(CommitteeVoting).filter(
        CommitteeVoting.committee_id == committee_id
    ).count()
    
    return {
        "committee_id": committee_id,
        "committee_name": committee.name,
        "active_members": members_count,
        "total_meetings": meetings_count,
        "total_activities": activities_count,
        "total_documents": documents_count,
        "total_votings": votings_count,
        "is_active": committee.is_active
    }
