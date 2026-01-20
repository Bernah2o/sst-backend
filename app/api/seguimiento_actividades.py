from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import os
from datetime import datetime

from app.database import get_db
from app.models import SeguimientoActividad, Seguimiento, User
from app.schemas.seguimiento_actividad import (
    SeguimientoActividadCreate,
    SeguimientoActividadUpdate,
    SeguimientoActividadResponse,
    SeguimientoActividadListResponse,
    ArchivoSoporteResponse,
    EstadoActividad,
    PrioridadActividad,
    TipoFecha
)
from app.schemas.common import MessageResponse
from app.dependencies import get_current_user, require_supervisor_or_admin
from app.utils.storage import storage_manager

router = APIRouter()

@router.get("/seguimiento/{seguimiento_id}/actividades", response_model=List[SeguimientoActividadListResponse])
def get_actividades_by_seguimiento(
    seguimiento_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    estado: Optional[EstadoActividad] = None,
    prioridad: Optional[PrioridadActividad] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtener todas las actividades de un seguimiento específico
    """
    # Verificar que el seguimiento existe
    seguimiento = db.query(Seguimiento).filter(Seguimiento.id == seguimiento_id).first()
    if not seguimiento:
        raise HTTPException(status_code=404, detail="Seguimiento no encontrado")
    
    query = db.query(SeguimientoActividad).filter(SeguimientoActividad.seguimiento_id == seguimiento_id)
    
    # Filtros opcionales
    if estado:
        query = query.filter(SeguimientoActividad.estado == estado)
    
    if prioridad:
        query = query.filter(SeguimientoActividad.prioridad == prioridad)
    
    actividades = query.offset(skip).limit(limit).all()
    return actividades

@router.get("/actividades/{actividad_id}", response_model=SeguimientoActividadResponse)
def get_actividad(
    actividad_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtener una actividad específica por ID
    """
    actividad = db.query(SeguimientoActividad).filter(SeguimientoActividad.id == actividad_id).first()
    if not actividad:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")
    return actividad

@router.post("/seguimiento/{seguimiento_id}/actividades", response_model=SeguimientoActividadResponse)
def create_actividad(
    seguimiento_id: int,
    actividad: SeguimientoActividadCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Crear una nueva actividad para un seguimiento
    """
    # Verificar que el seguimiento existe
    seguimiento = db.query(Seguimiento).filter(Seguimiento.id == seguimiento_id).first()
    if not seguimiento:
        raise HTTPException(status_code=404, detail="Seguimiento no encontrado")
    
    # Asegurar que el seguimiento_id coincida
    actividad.seguimiento_id = seguimiento_id
    
    db_actividad = SeguimientoActividad(**actividad.dict())
    db.add(db_actividad)
    db.commit()
    db.refresh(db_actividad)
    return db_actividad

@router.put("/actividades/{actividad_id}", response_model=SeguimientoActividadResponse)
def update_actividad(
    actividad_id: int,
    actividad_update: SeguimientoActividadUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Actualizar una actividad existente
    """
    db_actividad = db.query(SeguimientoActividad).filter(SeguimientoActividad.id == actividad_id).first()
    if not db_actividad:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")
    
    update_data = actividad_update.dict(exclude_unset=True)
    
    # Si se está marcando como completada, agregar información de completado
    if update_data.get('estado') == EstadoActividad.COMPLETADA:
        update_data['completada_por'] = current_user.id
        update_data['fecha_completada'] = datetime.utcnow()
    
    for field, value in update_data.items():
        setattr(db_actividad, field, value)
    
    db.commit()
    db.refresh(db_actividad)
    return db_actividad

@router.delete("/actividades/{actividad_id}")
async def delete_actividad(
    actividad_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Eliminar una actividad
    """
    db_actividad = db.query(SeguimientoActividad).filter(SeguimientoActividad.id == actividad_id).first()
    if not db_actividad:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")
    
    # Si tiene archivo de soporte, eliminarlo
    if db_actividad.archivo_soporte_url:
        try:
            # Extraer el path del archivo o usar la URL completa
             await storage_manager.delete_file(db_actividad.archivo_soporte_url)
        except Exception as e:
            # Log el error pero no fallar la eliminación de la actividad
            print(f"Error eliminando archivo de soporte: {str(e)}")
    
    db.delete(db_actividad)
    db.commit()
    return {"message": "Actividad eliminada exitosamente"}

@router.post("/actividades/{actividad_id}/upload-soporte", response_model=ArchivoSoporteResponse)
async def upload_archivo_soporte(
    actividad_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Subir archivo de soporte para una actividad
    """
    # Verificar que la actividad existe
    db_actividad = db.query(SeguimientoActividad).filter(SeguimientoActividad.id == actividad_id).first()
    if not db_actividad:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")
    
    # Validar tipo de archivo (solo PDFs)
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos PDF")
    
    try:
        # Subir archivo usando storage_manager
        result = await storage_manager.upload_file(
            file, 
            folder="seguimiento_actividades"
        )
        
        file_url = result.get("url")
        filename = result.get("filename")
        
        # Actualizar la actividad con la información del archivo
        db_actividad.archivo_soporte_url = file_url
        db_actividad.archivo_soporte_nombre = filename or file.filename
        db.commit()
        
        return ArchivoSoporteResponse(
            url=file_url,
            nombre_archivo=filename,
            mensaje="Archivo de soporte subido exitosamente"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error subiendo archivo: {str(e)}"
        )

@router.delete("/actividades/{actividad_id}/soporte")
async def delete_archivo_soporte(
    actividad_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Eliminar archivo de soporte de una actividad
    """
    db_actividad = db.query(SeguimientoActividad).filter(SeguimientoActividad.id == actividad_id).first()
    if not db_actividad:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")
    
    if not db_actividad.archivo_soporte_url:
        raise HTTPException(status_code=404, detail="No hay archivo de soporte para eliminar")
    
    try:
        # Eliminar archivo
        await storage_manager.delete_file(db_actividad.archivo_soporte_url)
        
        # Limpiar la información del archivo en la base de datos
        db_actividad.archivo_soporte_url = None
        db_actividad.archivo_soporte_nombre = None
        db.commit()
        
        return {"message": "Archivo de soporte eliminado exitosamente"}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error eliminando archivo: {str(e)}"
        )

@router.post("/actividades", response_model=SeguimientoActividadResponse)
def create_actividad_direct(
    actividad: SeguimientoActividadCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Crear una nueva actividad directamente (sin especificar seguimiento_id en la URL)
    """
    # Verificar que el seguimiento existe
    seguimiento = db.query(Seguimiento).filter(Seguimiento.id == actividad.seguimiento_id).first()
    if not seguimiento:
        raise HTTPException(status_code=404, detail="Seguimiento no encontrado")
    
    db_actividad = SeguimientoActividad(**actividad.dict())
    db.add(db_actividad)
    db.commit()
    db.refresh(db_actividad)
    return db_actividad

@router.get("/actividades", response_model=List[SeguimientoActividadListResponse])
def get_all_actividades(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    estado: Optional[EstadoActividad] = None,
    prioridad: Optional[PrioridadActividad] = None,
    responsable: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtener todas las actividades con filtros opcionales
    """
    query = db.query(SeguimientoActividad)
    
    # Filtros opcionales
    if estado:
        query = query.filter(SeguimientoActividad.estado == estado)
    
    if prioridad:
        query = query.filter(SeguimientoActividad.prioridad == prioridad)
    
    if responsable:
        query = query.filter(SeguimientoActividad.responsable.ilike(f"%{responsable}%"))
    
    actividades = query.offset(skip).limit(limit).all()
    return actividades