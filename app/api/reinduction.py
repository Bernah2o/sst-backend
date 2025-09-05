from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_supervisor_or_admin
from app.models.user import User
from app.models.reinduction import ReinductionRecord, ReinductionConfig
from app.schemas.reinduction import (
    ReinductionRecordCreate,
    ReinductionRecordUpdate,
    ReinductionRecordResponse,
    ReinductionConfigCreate,
    ReinductionConfigUpdate,
    ReinductionConfigResponse,
    WorkerReinductionSummary,
    ReinductionDashboard,
    BulkReinductionCreate,
    BulkReinductionResponse
)
from app.services.reinduction_service import ReinductionService
from app.scheduler import (
    get_scheduler_status,
    run_manual_check,
    start_scheduler,
    stop_scheduler
)

router = APIRouter()


@router.get("/dashboard", response_model=ReinductionDashboard)
def get_reinduction_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
):
    """Obtiene el dashboard con estadísticas de reinducción"""
    service = ReinductionService(db)
    return service.get_reinduction_dashboard()


@router.get("/records", response_model=List[ReinductionRecordResponse])
def get_reinduction_records(
    worker_id: Optional[int] = Query(None, description="Filtrar por ID de trabajador"),
    year: Optional[int] = Query(None, description="Filtrar por año"),
    status: Optional[str] = Query(None, description="Filtrar por estado"),
    search: Optional[str] = Query(None, description="Buscar por nombre o documento del trabajador"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
):
    """Obtiene la lista de registros de reinducción con filtros"""
    from app.models.worker import Worker
    from sqlalchemy import or_, func
    
    query = db.query(ReinductionRecord).join(Worker)
    
    if worker_id:
        query = query.filter(ReinductionRecord.worker_id == worker_id)
    if year:
        query = query.filter(ReinductionRecord.year == year)
    if status:
        query = query.filter(ReinductionRecord.status == status)
    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                func.concat(Worker.first_name, ' ', Worker.last_name).ilike(search_term),
                Worker.document_number.ilike(search_term),
                Worker.first_name.ilike(search_term),
                Worker.last_name.ilike(search_term)
            )
        )
    
    records = query.offset(skip).limit(limit).all()
    
    # Enriquecer con información adicional
    response_records = []
    for record in records:
        record_dict = {
            **record.__dict__,
            "is_overdue": record.is_overdue,
            "days_until_due": record.days_until_due,
            "needs_notification": record.needs_notification,
            "worker_name": record.worker.full_name if record.worker else None,
            "course_title": record.assigned_course.title if record.assigned_course else None,
            "enrollment_status": record.enrollment.status if record.enrollment else None
        }
        response_records.append(ReinductionRecordResponse(**record_dict))
    
    return response_records


@router.post("/records", response_model=ReinductionRecordResponse, status_code=status.HTTP_201_CREATED)
def create_reinduction_record(
    record_data: ReinductionRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
):
    """Crea un nuevo registro de reinducción"""
    service = ReinductionService(db)
    try:
        record = service.create_reinduction_record(record_data, current_user.id)
        
        # Enriquecer respuesta
        record_dict = {
            **record.__dict__,
            "is_overdue": record.is_overdue,
            "days_until_due": record.days_until_due,
            "needs_notification": record.needs_notification,
            "worker_name": record.worker.full_name if record.worker else None,
            "course_title": record.assigned_course.title if record.assigned_course else None
        }
        
        return ReinductionRecordResponse(**record_dict)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/records/{record_id}", response_model=ReinductionRecordResponse)
def update_reinduction_record(
    record_id: int,
    update_data: ReinductionRecordUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
):
    """Actualiza un registro de reinducción"""
    service = ReinductionService(db)
    try:
        record = service.update_reinduction_record(record_id, update_data)
        
        # Enriquecer respuesta
        record_dict = {
            **record.__dict__,
            "is_overdue": record.is_overdue,
            "days_until_due": record.days_until_due,
            "needs_notification": record.needs_notification,
            "worker_name": record.worker.full_name if record.worker else None,
            "course_title": record.assigned_course.title if record.assigned_course else None,
            "enrollment_status": record.enrollment.status if record.enrollment else None
        }
        
        return ReinductionRecordResponse(**record_dict)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/records/{record_id}", response_model=ReinductionRecordResponse)
def get_reinduction_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
):
    """Obtiene un registro de reinducción específico"""
    record = db.query(ReinductionRecord).filter(ReinductionRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Registro de reinducción no encontrado")
    
    # Enriquecer respuesta
    record_dict = {
        **record.__dict__,
        "is_overdue": record.is_overdue,
        "days_until_due": record.days_until_due,
        "needs_notification": record.needs_notification,
        "worker_name": record.worker.full_name if record.worker else None,
        "course_title": record.assigned_course.title if record.assigned_course else None,
        "enrollment_status": record.enrollment.status if record.enrollment else None
    }
    
    return ReinductionRecordResponse(**record_dict)


@router.post("/records/{record_id}/enroll")
def enroll_worker_in_reinduction(
    record_id: int,
    course_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
):
    """Inscribe a un trabajador en un curso de reinducción"""
    service = ReinductionService(db)
    try:
        enrollment = service.enroll_worker_in_reinduction(record_id, course_id)
        return {
            "message": "Trabajador inscrito exitosamente",
            "enrollment_id": enrollment.id,
            "course_id": enrollment.course_id
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bulk-create", response_model=BulkReinductionResponse)
def bulk_create_reinducciones(
    bulk_data: BulkReinductionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
):
    """Crea registros de reinducción en lote"""
    service = ReinductionService(db)
    try:
        result = service.bulk_create_reinducciones(bulk_data, current_user.id)
        
        # Enriquecer registros creados
        enriched_records = []
        for record in result["created_records"]:
            record_dict = {
                **record.__dict__,
                "is_overdue": record.is_overdue,
                "days_until_due": record.days_until_due,
                "needs_notification": record.needs_notification,
                "worker_name": record.worker.full_name if record.worker else None,
                "course_title": record.assigned_course.title if record.assigned_course else None
            }
            enriched_records.append(ReinductionRecordResponse(**record_dict))
        
        return BulkReinductionResponse(
            created_count=result["created_count"],
            updated_count=result["updated_count"],
            skipped_count=result["skipped_count"],
            errors=result["errors"],
            created_records=enriched_records
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/generate-missing")
def generate_missing_reinduction_records(
    worker_id: Optional[int] = Query(None, description="ID específico de trabajador (opcional)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
):
    """Genera registros de reinducción faltantes"""
    service = ReinductionService(db)
    try:
        result = service.generate_missing_reinduction_records(worker_id)
        return {
            "message": "Registros de reinducción generados exitosamente",
            "created": result["created"],
            "updated": result["updated"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workers/{worker_id}/summary", response_model=WorkerReinductionSummary)
def get_worker_reinduction_summary(
    worker_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
):
    """Obtiene el resumen de reinducción para un trabajador específico"""
    service = ReinductionService(db)
    try:
        return service.get_worker_reinduction_summary(worker_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/config", response_model=ReinductionConfigResponse)
def get_reinduction_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
):
    """Obtiene la configuración de reinducción"""
    service = ReinductionService(db)
    config = service.get_reinduction_config()
    
    # Enriquecer respuesta
    config_dict = {
        **config.__dict__,
        "default_course_title": config.default_course.title if config.default_course else None
    }
    
    return ReinductionConfigResponse(**config_dict)


@router.put("/config", response_model=ReinductionConfigResponse)
def update_reinduction_config(
    update_data: ReinductionConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
):
    """Actualiza la configuración de reinducción"""
    service = ReinductionService(db)
    try:
        config = service.update_reinduction_config(update_data, current_user.id)
        
        # Enriquecer respuesta
        config_dict = {
            **config.__dict__,
            "default_course_title": config.default_course.title if config.default_course else None
        }
        
        return ReinductionConfigResponse(**config_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Endpoints para gestión del scheduler
@router.get("/scheduler/status")
def get_scheduler_status_endpoint(
    current_user: User = Depends(require_supervisor_or_admin)
):
    """Obtiene el estado del scheduler de reinducciones"""
    return get_scheduler_status()


@router.post("/scheduler/start")
def start_scheduler_endpoint(
    current_user: User = Depends(require_supervisor_or_admin)
):
    """Inicia el scheduler de reinducciones"""
    try:
        start_scheduler()
        return {"message": "Scheduler iniciado exitosamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scheduler/stop")
def stop_scheduler_endpoint(
    current_user: User = Depends(require_supervisor_or_admin)
):
    """Detiene el scheduler de reinducciones"""
    try:
        stop_scheduler()
        return {"message": "Scheduler detenido exitosamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scheduler/run-manual-check")
def run_manual_check_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
):
    """Ejecuta una verificación manual inmediata"""
    try:
        result = run_manual_check()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-completion-webhook")
def test_completion_webhook(
    enrollment_id: int,
    current_user: User = Depends(require_supervisor_or_admin),
    db: Session = Depends(get_db)
):
    """Endpoint para probar la actualización automática de reinducción al completar curso"""
    try:
        from app.models.enrollment import Enrollment
        
        # Buscar la inscripción
        enrollment = db.query(Enrollment).filter(Enrollment.id == enrollment_id).first()
        if not enrollment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Enrollment not found"
            )
        
        # Simular completar la inscripción
        enrollment.complete_enrollment()
        db.commit()
        
        return {
            "message": "Webhook de completación ejecutado exitosamente",
            "enrollment_id": enrollment_id,
            "status": "completed"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error ejecutando webhook de completación: {str(e)}"
        )


@router.post("/send-anniversary-notification/{worker_id}")
def send_anniversary_notification(
    worker_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
):
    """Envía manualmente la notificación de aniversario para un trabajador específico"""
    service = ReinductionService(db)
    try:
        success = service.send_anniversary_notification(worker_id)
        if success:
            return {
                "message": f"Notificación de aniversario enviada exitosamente al trabajador {worker_id}",
                "worker_id": worker_id,
                "sent_by": current_user.id
            }
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"No se pudo enviar la notificación de aniversario al trabajador {worker_id}"
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check-completed")
def check_completed_reinducciones(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
):
    """Verifica y actualiza reinducciones completadas"""
    service = ReinductionService(db)
    try:
        updated_count = service.check_completed_reinducciones()
        return {
            "message": "Verificación completada",
            "updated_count": updated_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/send-notifications")
def send_reinduction_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
):
    """Envía notificaciones de reinducción pendientes"""
    service = ReinductionService(db)
    try:
        result = service.send_reinduction_notifications()
        return {
            "message": "Notificaciones procesadas",
            "sent": result["sent"],
            "errors": result["errors"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/regenerate-worker/{worker_id}")
def regenerate_worker_reinduction_records(
    worker_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin)
):
    """Regenera los registros de reinducción para un trabajador específico después de actualizar su fecha de ingreso"""
    from app.models.worker import Worker
    
    # Verificar que el trabajador existe
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajador no encontrado"
        )
    
    if not worker.fecha_de_ingreso:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El trabajador no tiene fecha de ingreso configurada"
        )
    
    service = ReinductionService(db)
    try:
        # Eliminar registros existentes que no estén completados
        from app.models.reinduction import ReinductionRecord, ReinductionStatus
        
        existing_records = db.query(ReinductionRecord).filter(
            ReinductionRecord.worker_id == worker_id,
            ReinductionRecord.status.in_([
                ReinductionStatus.PENDING,
                ReinductionStatus.SCHEDULED,
                ReinductionStatus.IN_PROGRESS,
                ReinductionStatus.OVERDUE
            ])
        ).all()
        
        deleted_count = len(existing_records)
        for record in existing_records:
            db.delete(record)
        
        db.commit()
        
        # Regenerar registros faltantes
        result = service.generate_missing_reinduction_records(worker_id=worker_id)
        
        return {
            "message": f"Registros de reinducción regenerados para el trabajador {worker.full_name}",
            "worker_id": worker_id,
            "worker_name": worker.full_name,
            "fecha_de_ingreso": worker.fecha_de_ingreso.isoformat(),
            "deleted_records": deleted_count,
            "created_records": result["created"],
            "updated_records": result["updated"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))