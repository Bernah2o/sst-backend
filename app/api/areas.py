from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.area import Area
from app.schemas.area import AreaCreate, AreaUpdate, Area as AreaSchema, AreaList
from app.api.auth import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/", response_model=AreaList)
def get_areas(
    skip: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(10, ge=1, le=100, description="Número de registros a devolver"),
    search: Optional[str] = Query(None, description="Buscar por nombre"),
    is_active: Optional[bool] = Query(None, description="Filtrar por estado activo"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtener lista paginada de áreas
    """
    query = db.query(Area)
    
    # Aplicar filtros
    if search:
        query = query.filter(Area.name.ilike(f"%{search}%"))
    
    if is_active is not None:
        query = query.filter(Area.is_active == is_active)
    
    # Obtener total de registros
    total = query.count()
    
    # Aplicar paginación
    areas = query.offset(skip).limit(limit).all()
    
    # Calcular información de paginación
    page = skip // limit + 1
    pages = (total + limit - 1) // limit
    
    return AreaList(
        items=areas,
        total=total,
        page=page,
        size=limit,
        pages=pages
    )


@router.get("/{area_id}", response_model=AreaSchema)
def get_area(
    area_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtener un área por ID
    """
    area = db.query(Area).filter(Area.id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Área no encontrada")
    return area


@router.post("/", response_model=AreaSchema)
def create_area(
    area: AreaCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Crear una nueva área
    """
    # Verificar si ya existe un área con el mismo nombre
    existing_area = db.query(Area).filter(Area.name == area.name).first()
    if existing_area:
        raise HTTPException(status_code=400, detail="Ya existe un área con este nombre")
    
    db_area = Area(**area.model_dump())
    db.add(db_area)
    db.commit()
    db.refresh(db_area)
    return db_area


@router.put("/{area_id}", response_model=AreaSchema)
def update_area(
    area_id: int,
    area_update: AreaUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Actualizar un área existente
    """
    db_area = db.query(Area).filter(Area.id == area_id).first()
    if not db_area:
        raise HTTPException(status_code=404, detail="Área no encontrada")
    
    # Verificar si el nuevo nombre ya existe (si se está cambiando)
    if area_update.name and area_update.name != db_area.name:
        existing_area = db.query(Area).filter(Area.name == area_update.name).first()
        if existing_area:
            raise HTTPException(status_code=400, detail="Ya existe un área con este nombre")
    
    # Actualizar solo los campos proporcionados
    update_data = area_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_area, field, value)
    
    db.commit()
    db.refresh(db_area)
    return db_area


@router.delete("/{area_id}")
def delete_area(
    area_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Eliminar un área
    """
    db_area = db.query(Area).filter(Area.id == area_id).first()
    if not db_area:
        raise HTTPException(status_code=404, detail="Área no encontrada")
    
    # Verificar si hay trabajadores asignados a esta área
    from app.models.worker import Worker
    workers_count = db.query(func.count(Worker.id)).filter(Worker.area_id == area_id).scalar()
    if workers_count > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"No se puede eliminar el área porque tiene {workers_count} trabajador(es) asignado(s)"
        )
    
    db.delete(db_area)
    db.commit()
    return {"message": "Área eliminada exitosamente"}


@router.get("/active/list", response_model=List[AreaSchema])
def get_active_areas(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtener lista de áreas activas (para selects/dropdowns)
    """
    areas = db.query(Area).filter(Area.is_active == True).order_by(Area.name).all()
    return areas