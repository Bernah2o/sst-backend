"""
API endpoints para Sectores Económicos.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.dependencies import get_current_active_user, require_admin
from app.models.sector_economico import SectorEconomico
from app.models.user import User
from app.schemas.sector_economico import (
    SectorEconomico as SectorEconomicoSchema,
    SectorEconomicoCreate,
    SectorEconomicoUpdate,
    SectorEconomicoSimple,
)

router = APIRouter()


@router.get("/", response_model=List[SectorEconomicoSchema])
def list_sectores_economicos(
    activo: Optional[bool] = Query(None, description="Filtrar por estado activo"),
    q: Optional[str] = Query(None, description="Buscar por nombre o código"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Lista todos los sectores económicos."""
    query = db.query(SectorEconomico)

    if activo is not None:
        query = query.filter(SectorEconomico.activo == activo)

    if q:
        search = f"%{q}%"
        query = query.filter(
            (SectorEconomico.nombre.ilike(search)) |
            (SectorEconomico.codigo.ilike(search))
        )

    return query.order_by(SectorEconomico.nombre).all()


@router.get("/activos", response_model=List[SectorEconomicoSimple])
def list_sectores_activos(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Lista solo los sectores económicos activos (para selectores)."""
    return db.query(SectorEconomico).filter(
        SectorEconomico.activo == True
    ).order_by(SectorEconomico.nombre).all()


@router.get("/{sector_id}", response_model=SectorEconomicoSchema)
def get_sector_economico(
    sector_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Obtiene un sector económico por ID."""
    sector = db.query(SectorEconomico).filter(
        SectorEconomico.id == sector_id
    ).first()

    if not sector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sector económico no encontrado"
        )

    return sector


@router.post("/", response_model=SectorEconomicoSchema, status_code=status.HTTP_201_CREATED)
def create_sector_economico(
    payload: SectorEconomicoCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Crea un nuevo sector económico."""
    # Verificar que no exista uno con el mismo nombre
    existing = db.query(SectorEconomico).filter(
        func.upper(SectorEconomico.nombre) == payload.nombre.upper()
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un sector económico con ese nombre"
        )

    # Verificar código único si se proporciona
    if payload.codigo:
        existing_codigo = db.query(SectorEconomico).filter(
            func.upper(SectorEconomico.codigo) == payload.codigo.upper()
        ).first()
        if existing_codigo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un sector económico con ese código"
            )

    sector = SectorEconomico(**payload.model_dump())
    db.add(sector)
    db.commit()
    db.refresh(sector)

    return sector


@router.put("/{sector_id}", response_model=SectorEconomicoSchema)
def update_sector_economico(
    sector_id: int,
    payload: SectorEconomicoUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Actualiza un sector económico."""
    sector = db.query(SectorEconomico).filter(
        SectorEconomico.id == sector_id
    ).first()

    if not sector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sector económico no encontrado"
        )

    # No permitir modificar el sector "TODOS LOS SECTORES"
    if sector.es_todos_los_sectores:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede modificar el sector 'TODOS LOS SECTORES'"
        )

    # Verificar nombre único si se está actualizando
    if payload.nombre:
        existing = db.query(SectorEconomico).filter(
            func.upper(SectorEconomico.nombre) == payload.nombre.upper(),
            SectorEconomico.id != sector_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un sector económico con ese nombre"
            )

    # Verificar código único si se está actualizando
    if payload.codigo:
        existing_codigo = db.query(SectorEconomico).filter(
            func.upper(SectorEconomico.codigo) == payload.codigo.upper(),
            SectorEconomico.id != sector_id
        ).first()
        if existing_codigo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un sector económico con ese código"
            )

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(sector, key, value)

    db.commit()
    db.refresh(sector)

    return sector


@router.delete("/{sector_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sector_economico(
    sector_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Elimina un sector económico."""
    sector = db.query(SectorEconomico).filter(
        SectorEconomico.id == sector_id
    ).first()

    if not sector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sector económico no encontrado"
        )

    # No permitir eliminar el sector "TODOS LOS SECTORES"
    if sector.es_todos_los_sectores:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar el sector 'TODOS LOS SECTORES'"
        )

    # Verificar si tiene empresas asociadas
    if sector.empresas:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar el sector porque tiene empresas asociadas"
        )

    # Verificar si tiene normas asociadas
    if sector.normas:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar el sector porque tiene normas asociadas"
        )

    db.delete(sector)
    db.commit()

    return None
