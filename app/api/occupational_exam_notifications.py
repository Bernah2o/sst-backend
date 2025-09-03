from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin, require_supervisor_or_admin
from app.models.user import User
from app.services.occupational_exam_notifications import OccupationalExamNotificationService
from app.scheduler.occupational_exam_scheduler import (
    get_occupational_exam_scheduler_status,
    run_manual_occupational_exam_check,
    start_occupational_exam_scheduler,
    stop_occupational_exam_scheduler
)
from app.schemas.common import MessageResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/send-daily-notifications", response_model=Dict[str, Any])
async def send_daily_notifications(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
) -> Any:
    """Enviar notificaciones diarias de exámenes ocupacionales manualmente"""
    try:
        service = OccupationalExamNotificationService(db)
        
        # Ejecutar en background para no bloquear la respuesta
        def send_notifications():
            return service.send_daily_notifications()
        
        background_tasks.add_task(send_notifications)
        
        return {
            "message": "Proceso de notificaciones iniciado en segundo plano",
            "status": "started"
        }
        
    except Exception as e:
        logger.error(f"Error iniciando notificaciones diarias: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error iniciando notificaciones: {str(e)}"
        )


@router.get("/pending-exams", response_model=Dict[str, Any])
async def get_pending_exams(
    days_ahead: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """Obtener lista de trabajadores con exámenes ocupacionales pendientes"""
    try:
        service = OccupationalExamNotificationService(db)
        workers_with_pending_exams = service.get_workers_with_pending_exams(days_ahead)
        
        # Formatear respuesta
        pending_exams = []
        for worker_data in workers_with_pending_exams:
            worker = worker_data["worker"]
            cargo = worker_data["cargo"]
            user = worker_data["user"]
            
            pending_exams.append({
                "worker_id": worker.id,
                "worker_name": worker.full_name,
                "worker_document": worker.document_number,
                "worker_email": user.email if user else None,
                "cargo": cargo.nombre_cargo,
                "periodicidad": cargo.periodicidad_emo,
                "last_exam_date": worker_data["last_exam_date"].isoformat() if worker_data["last_exam_date"] else None,
                "next_exam_date": worker_data["next_exam_date"].isoformat(),
                "days_until_exam": worker_data["days_until_exam"],
                "status": worker_data["status"]
            })
        
        return {
            "pending_exams": pending_exams,
            "total_count": len(pending_exams),
            "days_ahead": days_ahead
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo exámenes pendientes: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo exámenes pendientes: {str(e)}"
        )


@router.get("/statistics", response_model=Dict[str, Any])
async def get_exam_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """Obtener estadísticas de exámenes ocupacionales"""
    try:
        service = OccupationalExamNotificationService(db)
        stats = service.get_exam_statistics()
        
        return stats
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo estadísticas: {str(e)}"
        )


@router.post("/send-individual-reminder/{worker_id}", response_model=MessageResponse)
async def send_individual_reminder(
    worker_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """Enviar recordatorio individual a un trabajador específico"""
    try:
        service = OccupationalExamNotificationService(db)
        
        # Obtener datos del trabajador
        workers_with_pending_exams = service.get_workers_with_pending_exams(days_ahead=365)  # Buscar en un rango amplio
        worker_data = None
        
        for data in workers_with_pending_exams:
            if data["worker"].id == worker_id:
                worker_data = data
                break
        
        if not worker_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trabajador no encontrado o no requiere examen"
            )
        
        # Enviar recordatorio en background
        def send_reminder():
            return service.send_exam_reminder_email(worker_data)
        
        background_tasks.add_task(send_reminder)
        
        return MessageResponse(
            message=f"Recordatorio enviado a {worker_data['worker'].full_name}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enviando recordatorio individual: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error enviando recordatorio: {str(e)}"
        )


@router.post("/send-notification-with-pdf/{worker_id}", response_model=MessageResponse)
async def send_notification_with_pdf(
    worker_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
) -> Any:
    """Enviar notificación con PDF a un trabajador específico (alias para compatibilidad con frontend)"""
    try:
        service = OccupationalExamNotificationService(db)
        
        # Obtener datos del trabajador
        workers_with_pending_exams = service.get_workers_with_pending_exams(days_ahead=365)  # Buscar en un rango amplio
        worker_data = None
        
        for data in workers_with_pending_exams:
            if data["worker"].id == worker_id:
                worker_data = data
                break
        
        if not worker_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trabajador no encontrado o no requiere examen"
            )
        
        # Enviar recordatorio en background
        def send_reminder():
            return service.send_exam_reminder_email(worker_data)
        
        background_tasks.add_task(send_reminder)
        
        return MessageResponse(
            message=f"Notificación enviada a {worker_data['worker'].full_name}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enviando notificación: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error enviando notificación: {str(e)}"
        )


@router.get("/scheduler/status", response_model=Dict[str, Any])
async def get_scheduler_status(
    current_user: User = Depends(require_admin)
) -> Any:
    """Obtener estado del programador de tareas de exámenes ocupacionales"""
    try:
        status = get_occupational_exam_scheduler_status()
        return status
        
    except Exception as e:
        logger.error(f"Error obteniendo estado del programador: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo estado del programador: {str(e)}"
        )


@router.post("/scheduler/start", response_model=MessageResponse)
async def start_scheduler(
    current_user: User = Depends(require_admin)
) -> Any:
    """Iniciar el programador de tareas de exámenes ocupacionales"""
    try:
        start_occupational_exam_scheduler()
        return MessageResponse(message="Programador de exámenes ocupacionales iniciado")
        
    except Exception as e:
        logger.error(f"Error iniciando programador: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error iniciando programador: {str(e)}"
        )


@router.post("/scheduler/stop", response_model=MessageResponse)
async def stop_scheduler(
    current_user: User = Depends(require_admin)
) -> Any:
    """Detener el programador de tareas de exámenes ocupacionales"""
    try:
        stop_occupational_exam_scheduler()
        return MessageResponse(message="Programador de exámenes ocupacionales detenido")
        
    except Exception as e:
        logger.error(f"Error deteniendo programador: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deteniendo programador: {str(e)}"
        )


@router.post("/scheduler/run-manual-check", response_model=MessageResponse)
async def run_manual_check(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_admin)
) -> Any:
    """Ejecutar verificación manual de notificaciones de exámenes ocupacionales"""
    try:
        background_tasks.add_task(run_manual_occupational_exam_check)
        return MessageResponse(message="Verificación manual iniciada en segundo plano")
        
    except Exception as e:
        logger.error(f"Error ejecutando verificación manual: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error ejecutando verificación manual: {str(e)}"
        )