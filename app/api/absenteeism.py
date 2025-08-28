from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, extract

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Absenteeism, Worker, User
from app.schemas.absenteeism import (
    AbsenteeismCreate,
    AbsenteeismUpdate,
    AbsenteeismResponse,
    AbsenteeismWithWorker,
    AbsenteeismList,
    AbsenteeismStats,
)
from app.models.absenteeism import EventMonth, EventType

router = APIRouter(tags=["absenteeism"])


@router.post("/", response_model=AbsenteeismResponse, status_code=status.HTTP_201_CREATED)
def create_absenteeism(
    absenteeism_data: AbsenteeismCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Crear un nuevo registro de ausentismo"""
    
    # Debug logging
    print(f"DEBUG: Received absenteeism_data: {absenteeism_data}")
    print(f"DEBUG: absenteeism_data.model_dump(): {absenteeism_data.model_dump()}")
    print(f"DEBUG: disability_or_charged_days value: {getattr(absenteeism_data, 'disability_or_charged_days', 'NOT_FOUND')}")
    
    # Verificar que el trabajador existe
    worker = db.query(Worker).filter(Worker.id == absenteeism_data.worker_id).first()
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajador no encontrado"
        )
    
    # Crear el registro de ausentismo
    db_absenteeism = Absenteeism(**absenteeism_data.model_dump())
    db.add(db_absenteeism)
    db.commit()
    db.refresh(db_absenteeism)
    
    # Cargar la relación con el trabajador para obtener los campos calculados
    db_absenteeism = db.query(Absenteeism).options(
        joinedload(Absenteeism.worker)
    ).filter(Absenteeism.id == db_absenteeism.id).first()
    
    return db_absenteeism


@router.get("/", response_model=AbsenteeismList)
def get_absenteeism_list(
    skip: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(100, ge=1, le=1000, description="Número máximo de registros a devolver"),
    worker_id: Optional[int] = Query(None, description="Filtrar por ID del trabajador"),
    event_type: Optional[EventType] = Query(None, description="Filtrar por tipo de evento"),
    event_month: Optional[EventMonth] = Query(None, description="Filtrar por mes del evento"),
    start_date_from: Optional[date] = Query(None, description="Filtrar por fecha inicial desde"),
    start_date_to: Optional[date] = Query(None, description="Filtrar por fecha inicial hasta"),
    search: Optional[str] = Query(None, description="Buscar por nombre del trabajador o cédula"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener lista paginada de registros de ausentismo"""
    
    query = db.query(Absenteeism).options(
        joinedload(Absenteeism.worker)
    )
    
    # Aplicar filtros
    if worker_id:
        query = query.filter(Absenteeism.worker_id == worker_id)
    
    if event_type:
        query = query.filter(Absenteeism.event_type == event_type)
    
    if event_month:
        query = query.filter(Absenteeism.event_month == event_month)
    
    if start_date_from:
        query = query.filter(Absenteeism.start_date >= start_date_from)
    
    if start_date_to:
        query = query.filter(Absenteeism.start_date <= start_date_to)
    
    if search:
        query = query.join(Worker).filter(
            or_(
                func.concat(Worker.first_name, ' ', Worker.last_name).ilike(f"%{search}%"),
                Worker.document_number.ilike(f"%{search}%"),
                Worker.cedula.ilike(f"%{search}%")
            )
        )
    
    # Contar total de registros
    total = query.count()
    
    # Aplicar paginación
    items = query.offset(skip).limit(limit).all()
    
    # Convertir a esquema con información del trabajador
    items_with_worker = []
    for item in items:
        item_dict = {
            **item.__dict__,
            "worker_name": item.worker.full_name if item.worker else None,
            "worker_email": item.worker.email if item.worker else None,
            "worker_phone": item.worker.phone if item.worker else None,
            "cedula": item.worker.cedula or item.worker.document_number if item.worker else None,
            "cargo": item.worker.cargo or item.worker.position if item.worker else None,
            "base_salary": item.worker.salario or item.worker.salary_ibc if item.worker else None,
        }
        items_with_worker.append(AbsenteeismWithWorker(**item_dict))
    
    return AbsenteeismList(
        items=items_with_worker,
        total=total,
        page=skip // limit + 1,
        size=limit,
        pages=(total + limit - 1) // limit
    )


@router.get("/{absenteeism_id}", response_model=AbsenteeismWithWorker)
def get_absenteeism(
    absenteeism_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener un registro de ausentismo por ID"""
    
    absenteeism = db.query(Absenteeism).options(
        joinedload(Absenteeism.worker)
    ).filter(Absenteeism.id == absenteeism_id).first()
    
    if not absenteeism:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registro de ausentismo no encontrado"
        )
    
    # Agregar información del trabajador
    absenteeism_dict = {
        **absenteeism.__dict__,
        "worker_name": absenteeism.worker.full_name if absenteeism.worker else None,
        "worker_email": absenteeism.worker.email if absenteeism.worker else None,
        "worker_phone": absenteeism.worker.phone if absenteeism.worker else None,
        "cedula": absenteeism.worker.cedula or absenteeism.worker.document_number if absenteeism.worker else None,
        "cargo": absenteeism.worker.cargo or absenteeism.worker.position if absenteeism.worker else None,
        "base_salary": absenteeism.worker.salario or absenteeism.worker.salary_ibc if absenteeism.worker else None,
    }
    
    return AbsenteeismWithWorker(**absenteeism_dict)


@router.put("/{absenteeism_id}", response_model=AbsenteeismWithWorker)
def update_absenteeism(
    absenteeism_id: int,
    absenteeism_data: AbsenteeismUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Actualizar un registro de ausentismo"""
    
    absenteeism = db.query(Absenteeism).filter(Absenteeism.id == absenteeism_id).first()
    if not absenteeism:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registro de ausentismo no encontrado"
        )
    
    # Verificar que el trabajador existe si se está actualizando
    if absenteeism_data.worker_id:
        worker = db.query(Worker).filter(Worker.id == absenteeism_data.worker_id).first()
        if not worker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trabajador no encontrado"
            )
    
    # Actualizar campos
    update_data = absenteeism_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(absenteeism, field, value)
    
    db.commit()
    db.refresh(absenteeism)
    
    # Cargar la relación con el trabajador
    absenteeism = db.query(Absenteeism).options(
        joinedload(Absenteeism.worker)
    ).filter(Absenteeism.id == absenteeism_id).first()
    
    # Agregar información del trabajador
    absenteeism_dict = {
        **absenteeism.__dict__,
        "worker_name": absenteeism.worker.full_name if absenteeism.worker else None,
        "worker_email": absenteeism.worker.email if absenteeism.worker else None,
        "worker_phone": absenteeism.worker.phone if absenteeism.worker else None,
        "cedula": absenteeism.worker.cedula or absenteeism.worker.document_number if absenteeism.worker else None,
        "cargo": absenteeism.worker.cargo or absenteeism.worker.position if absenteeism.worker else None,
        "base_salary": absenteeism.worker.salario or absenteeism.worker.salary_ibc if absenteeism.worker else None,
    }
    
    return AbsenteeismWithWorker(**absenteeism_dict)


@router.delete("/{absenteeism_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_absenteeism(
    absenteeism_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Eliminar un registro de ausentismo"""
    
    absenteeism = db.query(Absenteeism).filter(Absenteeism.id == absenteeism_id).first()
    if not absenteeism:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registro de ausentismo no encontrado"
        )
    
    db.delete(absenteeism)
    db.commit()


@router.get("/stats/summary", response_model=AbsenteeismStats)
def get_absenteeism_stats(
    year: Optional[int] = Query(None, description="Filtrar por año"),
    worker_id: Optional[int] = Query(None, description="Filtrar por trabajador"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener estadísticas de ausentismo"""
    
    query = db.query(Absenteeism)
    
    # Aplicar filtros
    if year:
        query = query.filter(extract('year', Absenteeism.start_date) == year)
    
    if worker_id:
        query = query.filter(Absenteeism.worker_id == worker_id)
    
    # Estadísticas básicas
    total_records = query.count()
    total_disability_days = query.with_entities(func.sum(Absenteeism.disability_days)).scalar() or 0
    total_costs_at = query.with_entities(
        func.sum(Absenteeism.insured_costs_at + Absenteeism.assumed_costs_at)
    ).scalar() or 0
    total_costs_ac_eg = query.with_entities(
        func.sum(Absenteeism.insured_costs_ac_eg + Absenteeism.assumed_costs_ac_eg)
    ).scalar() or 0
    
    # Estadísticas por tipo de evento
    by_event_type = {}
    for event_type in EventType:
        count = query.filter(Absenteeism.event_type == event_type).count()
        by_event_type[event_type.value] = count
    
    # Estadísticas por mes
    by_month = {}
    for month in EventMonth:
        count = query.filter(Absenteeism.event_month == month).count()
        by_month[month.value] = count
    
    return AbsenteeismStats(
        total_records=total_records,
        total_disability_days=total_disability_days,
        total_costs_at=total_costs_at,
        total_costs_ac_eg=total_costs_ac_eg,
        by_event_type=by_event_type,
        by_month=by_month
    )


@router.get("/workers/search", response_model=List[dict])
def search_workers(
    q: str = Query(..., min_length=2, description="Término de búsqueda"),
    limit: int = Query(10, ge=1, le=50, description="Número máximo de resultados"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Buscar trabajadores para selección en formularios"""
    
    workers = db.query(Worker).filter(
        and_(
            Worker.is_active == True,
            or_(
                func.concat(Worker.first_name, ' ', Worker.last_name).ilike(f"%{q}%"),
                Worker.document_number.ilike(f"%{q}%"),
                Worker.cedula.ilike(f"%{q}%"),
                Worker.email.ilike(f"%{q}%")
            )
        )
    ).limit(limit).all()
    
    return [
        {
            "id": worker.id,
            "name": worker.full_name,
            "cedula": worker.cedula or worker.document_number,
            "cargo": worker.cargo or worker.position,
            "email": worker.email,
            "salario": float(worker.salario or worker.salary_ibc or 0)
        }
        for worker in workers
    ]