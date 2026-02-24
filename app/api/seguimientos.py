from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import os

from app.database import get_db
from app.models import (
    Seguimiento, Worker, EstadoSeguimiento, ValoracionRiesgo, OccupationalExam,
    Notification, NotificationType, NotificationPriority
)
from app.schemas.seguimiento import (
    SeguimientoCreate,
    SeguimientoUpdate,
    SeguimientoResponse,
)
from app.schemas.common import MessageResponse
from app.dependencies import get_current_user, require_supervisor_or_admin
from app.models.user import User
from app.services.medical_recommendation_generator import MedicalRecommendationGenerator

router = APIRouter()


@router.get("", response_model=List[SeguimientoResponse])
@router.get("/", response_model=List[SeguimientoResponse])
def get_seguimientos(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    estado: Optional[EstadoSeguimiento] = None,
    valoracion_riesgo: Optional[ValoracionRiesgo] = None,
    programa: Optional[str] = None,
    worker_id: Optional[int] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtener lista de seguimientos con filtros opcionales
    """
    query = db.query(Seguimiento)

    # Filtros
    if estado:
        query = query.filter(Seguimiento.estado == estado)

    if valoracion_riesgo:
        query = query.filter(Seguimiento.valoracion_riesgo == valoracion_riesgo)

    if programa:
        query = query.filter(Seguimiento.programa == programa)

    if worker_id:
        query = query.filter(Seguimiento.worker_id == worker_id)

    if search:
        search_filter = or_(
            Seguimiento.nombre_trabajador.ilike(f"%{search}%"),
            Seguimiento.cedula.ilike(f"%{search}%"),
            Seguimiento.cargo.ilike(f"%{search}%"),
            Seguimiento.programa.ilike(f"%{search}%"),
        )
        query = query.filter(search_filter)

    seguimientos = (
        query.order_by(Seguimiento.created_at.desc()).offset(skip).limit(limit).all()
    )
    return seguimientos


@router.get("/{seguimiento_id}", response_model=SeguimientoResponse)
def get_seguimiento(
    seguimiento_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtener un seguimiento específico por ID
    """
    seguimiento = db.query(Seguimiento).filter(Seguimiento.id == seguimiento_id).first()
    if not seguimiento:
        raise HTTPException(status_code=404, detail="Seguimiento no encontrado")
    return seguimiento


@router.get("/worker/{worker_id}", response_model=List[SeguimientoResponse])
def get_seguimientos_by_worker(
    worker_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtener todos los seguimientos de un trabajador específico (historial)
    """
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Trabajador no encontrado")

    seguimientos = (
        db.query(Seguimiento)
        .filter(Seguimiento.worker_id == worker_id)
        .order_by(Seguimiento.created_at.desc())
        .all()
    )

    return seguimientos


@router.post("/", response_model=SeguimientoResponse)
def create_seguimiento(
    seguimiento: SeguimientoCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Crear un nuevo seguimiento
    """
    # Verificar que el trabajador existe
    worker = db.query(Worker).filter(Worker.id == seguimiento.worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Trabajador no encontrado")

    db_seguimiento = Seguimiento(**seguimiento.dict())
    db.add(db_seguimiento)
    
    # Si se crea directamente en estado terminado, actualizar el programa del examen ocupacional y desmarcar seguimiento
    if db_seguimiento.estado == EstadoSeguimiento.TERMINADO and db_seguimiento.occupational_exam_id:
        db.query(OccupationalExam).filter(OccupationalExam.id == db_seguimiento.occupational_exam_id).update({
            "programa": "NINGUNO",
            "requires_follow_up": False
        })
        
    db.commit()
    db.refresh(db_seguimiento)
    return db_seguimiento


@router.put("/{seguimiento_id}", response_model=SeguimientoResponse)
def update_seguimiento(
    seguimiento_id: int,
    seguimiento_update: SeguimientoUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Actualizar un seguimiento existente
    """
    db_seguimiento = (
        db.query(Seguimiento).filter(Seguimiento.id == seguimiento_id).first()
    )
    if not db_seguimiento:
        raise HTTPException(status_code=404, detail="Seguimiento no encontrado")

    update_data = seguimiento_update.dict(exclude_unset=True)
    
    # Verificar si el estado está cambiando a terminado
    changing_to_terminado = update_data.get('estado') == EstadoSeguimiento.TERMINADO
    
    for field, value in update_data.items():
        setattr(db_seguimiento, field, value)

    # Si el seguimiento pasa a terminado, actualizar el programa del examen ocupacional a NINGUNO y desmarcar seguimiento
    if changing_to_terminado and db_seguimiento.occupational_exam_id:
        db.query(OccupationalExam).filter(OccupationalExam.id == db_seguimiento.occupational_exam_id).update({
            "programa": "NINGUNO",
            "requires_follow_up": False
        })

    db.commit()
    db.refresh(db_seguimiento)
    return db_seguimiento


@router.delete("/{seguimiento_id}")
def delete_seguimiento(
    seguimiento_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Eliminar un seguimiento
    """
    db_seguimiento = (
        db.query(Seguimiento).filter(Seguimiento.id == seguimiento_id).first()
    )
    if not db_seguimiento:
        raise HTTPException(status_code=404, detail="Seguimiento no encontrado")

    db.delete(db_seguimiento)
    db.commit()
    return {"message": "Seguimiento eliminado exitosamente"}


@router.post("/auto-create/{worker_id}")
def auto_create_seguimiento(
    worker_id: int,
    programa: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Crear automáticamente un seguimiento cuando se asigna un programa a un trabajador
    """
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Trabajador no encontrado")

    # Verificar si ya existe un seguimiento activo para este programa
    existing_seguimiento = (
        db.query(Seguimiento)
        .filter(
            and_(
                Seguimiento.worker_id == worker_id,
                Seguimiento.programa == programa,
                Seguimiento.estado == EstadoSeguimiento.INICIADO,
            )
        )
        .first()
    )

    if existing_seguimiento:
        raise HTTPException(
            status_code=400, detail="Ya existe un seguimiento activo para este programa"
        )

    # Crear nuevo seguimiento automáticamente
    seguimiento_data = {
        "worker_id": worker_id,
        "programa": programa,
        "nombre_trabajador": worker.full_name,
        "cedula": worker.document_number,
        "cargo": worker.position,
        "fecha_ingreso": worker.fecha_de_ingreso,
        "estado": EstadoSeguimiento.INICIADO,
    }

    db_seguimiento = Seguimiento(**seguimiento_data)
    db.add(db_seguimiento)
    db.commit()
    db.refresh(db_seguimiento)

    return {
        "message": "Seguimiento creado automáticamente",
        "seguimiento": db_seguimiento,
    }


@router.post(
    "/{seguimiento_id}/generate-medical-recommendation", response_model=MessageResponse
)
async def generate_medical_recommendation_pdf(
    seguimiento_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
):
    """
    Generar PDF de notificación de recomendaciones médicas para un seguimiento
    """
    # Verificar que el seguimiento existe
    seguimiento = db.query(Seguimiento).filter(Seguimiento.id == seguimiento_id).first()
    if not seguimiento:
        raise HTTPException(status_code=404, detail="Seguimiento no encontrado")

    try:
        # Generar el PDF
        generator = MedicalRecommendationGenerator(db)
        filepath = await generator.generate_medical_recommendation_pdf(seguimiento_id)

        return {
            "message": "PDF de recomendaciones médicas generado exitosamente",
            "filename": os.path.basename(filepath),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando el PDF: {str(e)}")


@router.get("/{seguimiento_id}/download-medical-recommendation")
async def download_medical_recommendation_pdf(
    seguimiento_id: int,
    download: bool = Query(
        True, description="Set to true to download the file with a custom filename"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
) -> FileResponse:
    """
    Descargar PDF de notificación de recomendaciones médicas
    """
    # Verificar que el seguimiento existe
    seguimiento = db.query(Seguimiento).filter(Seguimiento.id == seguimiento_id).first()
    if not seguimiento:
        raise HTTPException(status_code=404, detail="Seguimiento no encontrado")

    try:
        from app.config import settings

        # Generar el PDF si no existe
        generator = MedicalRecommendationGenerator(db)
        result = await generator.generate_medical_recommendation_pdf(seguimiento_id)

        # Obtener información del trabajador para el nombre del archivo
        worker = db.query(Worker).filter(Worker.id == seguimiento.worker_id).first()
        filename = f"recomendaciones_medicas_{worker.document_number if worker else seguimiento_id}.pdf"

        # result es una ruta relativa
        # Construir la ruta absoluta del archivo local
        local_filepath = os.path.join(
            generator.reports_dir, os.path.basename(result)
        )

        if not os.path.exists(local_filepath):
            raise HTTPException(status_code=404, detail="Archivo PDF no encontrado")

        # Preparar parámetros de respuesta
        response_params = {"path": local_filepath, "media_type": "application/pdf"}

        # Si se solicita descarga, agregar un nombre de archivo personalizado
        if download:
            response_params["filename"] = filename

        # Devolver respuesta de archivo con los parámetros apropiados
        return FileResponse(**response_params)

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error descargando el PDF: {str(e)}"
        )


@router.post("/{seguimiento_id}/notify-worker", response_model=MessageResponse)
async def notify_worker_inclusion(
    seguimiento_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
):
    """
    Enviar notificación al trabajador sobre su inclusión en el seguimiento
    """
    # 1. Obtener seguimiento
    seguimiento = db.query(Seguimiento).filter(Seguimiento.id == seguimiento_id).first()
    if not seguimiento:
        raise HTTPException(status_code=404, detail="Seguimiento no encontrado")

    # 2. Obtener trabajador
    worker = db.query(Worker).filter(Worker.id == seguimiento.worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Trabajador no encontrado")

    if not worker.email:
        raise HTTPException(
            status_code=400,
            detail="El trabajador no tiene un correo electrónico registrado",
        )

    # 3. Preparar contexto para el correo
    from app.config import settings
    from app.utils.email import send_email
    import json

    context = {
        "worker_name": worker.full_name,
        "programa": seguimiento.programa,
        "fecha_inicio": (
            seguimiento.fecha_inicio.strftime("%d/%m/%Y")
            if seguimiento.fecha_inicio
            else "Pendiente"
        ),
        "valoracion_riesgo": (
            seguimiento.valoracion_riesgo.title() if seguimiento.valoracion_riesgo else None
        ),
        "motivo_inclusion": seguimiento.motivo_inclusion,
        "system_url": settings.react_app_api_url,  # O la URL del frontend si es diferente
    }

    # 4. Enviar correo en segundo plano
    background_tasks.add_task(
        send_email,
        recipient=worker.email,
        subject="Notificación de Inclusión a Programa de Seguimiento SST",
        template="seguimiento_inclusion",
        context=context,
    )

    # 5. Crear notificación en el sistema
    notification = Notification(
        user_id=worker.user_id,
        title="Inclusión a Seguimiento SST",
        message=f"Has sido incluido en el programa de seguimiento: {seguimiento.programa}",
        notification_type=NotificationType.EMAIL,
        priority=NotificationPriority.NORMAL,
        additional_data=json.dumps({"seguimiento_id": seguimiento.id}),
    )
    db.add(notification)
    db.commit()

    return {"message": f"Notificación enviada exitosamente a {worker.email}"}
