from datetime import datetime, date, timedelta
from typing import List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models.user import User
from app.models.worker import Worker
from app.models.occupational_exam import OccupationalExam
from app.models.cargo import Cargo
from app.models.notification_acknowledgment import NotificationAcknowledgment
from app.schemas.admin_notifications import (
    WorkerExamNotificationResponse,
    NotificationSendRequest,
    NotificationSendResponse,
    NotificationSuppressionRequest,
    NotificationSuppressionResponse,
    NotificationAcknowledgmentResponse,
    NotificationStatistics,
    NotificationFilters,
    BulkNotificationAction,
    BulkNotificationResponse,
    ExamStatus,
    NotificationStatus,
    NotificationTypeEnum
)
from app.services.occupational_exam_notifications import OccupationalExamNotificationService
from app.schemas.common import MessageResponse

router = APIRouter(prefix="/admin/notifications", tags=["Admin Notifications"])


def verify_admin_permissions(current_user: User):
    """Verifica que el usuario actual sea administrador"""
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para administrar notificaciones"
        )


def calculate_next_exam_date(exam_date: date, periodicidad: str) -> date:
    """Calcula la fecha del próximo examen basado en la periodicidad"""
    if periodicidad == "semestral":
        return exam_date + timedelta(days=180)
    elif periodicidad == "anual":
        return exam_date + timedelta(days=365)
    elif periodicidad == "bianual":
        return exam_date + timedelta(days=730)
    else:
        return exam_date + timedelta(days=365)


def determine_exam_status(next_exam_date: date, last_exam_date: Optional[date]) -> ExamStatus:
    """Determina el estado del examen basado en las fechas"""
    today = date.today()
    
    if not last_exam_date:
        return ExamStatus.SIN_EXAMENES
    
    days_until_exam = (next_exam_date - today).days
    
    if days_until_exam <= 0:
        return ExamStatus.VENCIDO
    elif days_until_exam <= 30:
        return ExamStatus.PROXIMO_A_VENCER
    else:
        return ExamStatus.AL_DIA


@router.get("/exam-notifications", response_model=List[WorkerExamNotificationResponse])
async def get_exam_notifications(
    filters: NotificationFilters = Depends(),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Obtiene la lista de trabajadores y el estado de sus notificaciones de exámenes ocupacionales.
    Permite filtrar y paginar los resultados.
    """
    verify_admin_permissions(current_user)
    
    # Subconsulta para obtener el último examen de cada trabajador
    latest_exams_subq = (
        db.query(
            OccupationalExam.worker_id,
            func.max(OccupationalExam.exam_date).label('last_exam_date')
        )
        .group_by(OccupationalExam.worker_id)
        .subquery()
    )
    
    # Consulta principal
    query = (
        db.query(
            Worker,
            Cargo,
            latest_exams_subq.c.last_exam_date,
            User.email
        )
        .join(Cargo, Worker.position == Cargo.nombre_cargo)
        .outerjoin(latest_exams_subq, Worker.id == latest_exams_subq.c.worker_id)
        .outerjoin(User, Worker.document_number == User.document_number)
        .filter(Worker.is_active == True)
    )
    
    # Aplicar filtros
    if filters.position:
        query = query.filter(Worker.position.ilike(f"%{filters.position}%"))
    
    if filters.has_email is not None:
        if filters.has_email:
            query = query.filter(User.email.isnot(None))
        else:
            query = query.filter(User.email.is_(None))
    
    results = query.offset(skip).limit(limit).all()
    
    notifications = []
    today = date.today()
    
    for worker, cargo, last_exam_date, email in results:
        # Calcular próxima fecha de examen
        if last_exam_date:
            next_exam_date = calculate_next_exam_date(last_exam_date, cargo.periodicidad_emo or "anual")
        else:
            next_exam_date = today  # Necesita examen inmediatamente
        
        days_until_exam = (next_exam_date - today).days
        exam_status = determine_exam_status(next_exam_date, last_exam_date)
        
        # Aplicar filtros de estado
        if filters.exam_status and exam_status != filters.exam_status:
            continue
        
        if filters.days_until_exam_min is not None and days_until_exam < filters.days_until_exam_min:
            continue
        
        if filters.days_until_exam_max is not None and days_until_exam > filters.days_until_exam_max:
            continue
        
        # Obtener información de confirmaciones
        acknowledgments = db.query(NotificationAcknowledgment).filter(
            NotificationAcknowledgment.worker_id == worker.id
        ).all()
        
        acknowledgment_count = len(acknowledgments)
        notification_types_sent = list(set([ack.notification_type for ack in acknowledgments]))
        last_acknowledgment = max(acknowledgments, key=lambda x: x.acknowledged_at) if acknowledgments else None
        
        # Determinar si se puede enviar notificación
        can_send_notification = email is not None
        
        # Determinar estado de notificación
        if acknowledgments and any(ack.stops_notifications for ack in acknowledgments):
            notification_status = NotificationStatus.ACKNOWLEDGED
        elif exam_status == ExamStatus.AL_DIA:
            notification_status = NotificationStatus.PENDING
        else:
            notification_status = NotificationStatus.PENDING
        
        # Aplicar filtro de confirmación
        if filters.acknowledged is not None:
            has_acknowledgment = acknowledgment_count > 0
            if filters.acknowledged != has_acknowledgment:
                continue
        
        # Aplicar filtro de estado de notificación
        if filters.notification_status and notification_status != filters.notification_status:
            continue
        
        notifications.append(WorkerExamNotificationResponse(
            worker_id=worker.id,
            worker_name=worker.full_name,
            worker_document=worker.document_number,
            worker_position=worker.position,
            worker_email=email,
            last_exam_date=last_exam_date,
            next_exam_date=next_exam_date,
            days_until_exam=days_until_exam,
            exam_status=exam_status,
            periodicidad=cargo.periodicidad_emo or "anual",
            notification_status=notification_status,
            last_notification_sent=last_acknowledgment.acknowledged_at if last_acknowledgment else None,
            acknowledgment_count=acknowledgment_count,
            can_send_notification=can_send_notification,
            notification_types_sent=notification_types_sent,
            last_acknowledgment_date=last_acknowledgment.acknowledged_at if last_acknowledgment else None
        ))
    
    return notifications


@router.post("/send-notifications", response_model=NotificationSendResponse)
async def send_notifications(
    request: NotificationSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Envía notificaciones de exámenes ocupacionales a trabajadores específicos.
    """
    verify_admin_permissions(current_user)
    
    service = OccupationalExamNotificationService(db)
    
    stats = {
        "total_requested": len(request.worker_ids),
        "emails_sent": 0,
        "emails_failed": 0,
        "already_acknowledged": 0,
        "invalid_workers": 0,
        "details": []
    }
    
    for worker_id in request.worker_ids:
        try:
            # Obtener trabajador
            worker = db.query(Worker).filter(Worker.id == worker_id).first()
            if not worker:
                stats["invalid_workers"] += 1
                stats["details"].append({
                    "worker_id": worker_id,
                    "status": "error",
                    "message": "Trabajador no encontrado"
                })
                continue
            
            # Obtener usuario asociado
            user = db.query(User).filter(User.document_number == worker.document_number).first()
            if not user or not user.email:
                stats["invalid_workers"] += 1
                stats["details"].append({
                    "worker_id": worker_id,
                    "worker_name": worker.full_name,
                    "status": "error",
                    "message": "Trabajador sin email registrado"
                })
                continue
            
            # Verificar confirmaciones existentes si no es forzado
            if not request.force_send:
                latest_exam = db.query(OccupationalExam).filter(
                    OccupationalExam.worker_id == worker_id
                ).order_by(OccupationalExam.exam_date.desc()).first()
                
                if latest_exam:
                    existing_ack = db.query(NotificationAcknowledgment).filter(
                        and_(
                            NotificationAcknowledgment.worker_id == worker_id,
                            NotificationAcknowledgment.occupational_exam_id == latest_exam.id,
                            NotificationAcknowledgment.notification_type == request.notification_type.value,
                            NotificationAcknowledgment.stops_notifications == True
                        )
                    ).first()
                    
                    if existing_ack:
                        stats["already_acknowledged"] += 1
                        stats["details"].append({
                            "worker_id": worker_id,
                            "worker_name": worker.full_name,
                            "status": "skipped",
                            "message": f"Ya confirmó recepción de {request.notification_type.value}"
                        })
                        continue
            
            # Obtener datos del trabajador para el envío
            cargo = db.query(Cargo).filter(Cargo.nombre_cargo == worker.position).first()
            if not cargo:
                stats["invalid_workers"] += 1
                stats["details"].append({
                    "worker_id": worker_id,
                    "worker_name": worker.full_name,
                    "status": "error",
                    "message": "Cargo no encontrado"
                })
                continue
            
            # Calcular fechas
            latest_exam = db.query(OccupationalExam).filter(
                OccupationalExam.worker_id == worker_id
            ).order_by(OccupationalExam.exam_date.desc()).first()
            
            if latest_exam:
                next_exam_date = calculate_next_exam_date(
                    latest_exam.exam_date, 
                    cargo.periodicidad_emo or "anual"
                )
            else:
                next_exam_date = date.today()
            
            days_until_exam = (next_exam_date - date.today()).days
            
            if not latest_exam:
                status = "sin_examenes"
            elif days_until_exam <= 0:
                status = "vencido"
            else:
                status = "proximo_a_vencer"
            
            # Preparar datos para el servicio
            worker_data = {
                "worker": worker,
                "cargo": cargo,
                "user": user,
                "last_exam_date": latest_exam.exam_date if latest_exam else None,
                "next_exam_date": next_exam_date,
                "days_until_exam": days_until_exam,
                "status": status
            }
            
            # Enviar notificación
            if service.send_exam_reminder_email(worker_data):
                stats["emails_sent"] += 1
                stats["details"].append({
                    "worker_id": worker_id,
                    "worker_name": worker.full_name,
                    "worker_email": user.email,
                    "status": "sent",
                    "message": f"Notificación {request.notification_type.value} enviada exitosamente"
                })
            else:
                stats["emails_failed"] += 1
                stats["details"].append({
                    "worker_id": worker_id,
                    "worker_name": worker.full_name,
                    "worker_email": user.email,
                    "status": "failed",
                    "message": "Error enviando correo electrónico"
                })
                
        except Exception as e:
            stats["emails_failed"] += 1
            stats["details"].append({
                "worker_id": worker_id,
                "status": "error",
                "message": f"Error procesando trabajador: {str(e)}"
            })
    
    return NotificationSendResponse(**stats)


@router.post("/suppress-notifications", response_model=NotificationSuppressionResponse)
async def suppress_notifications(
    request: NotificationSuppressionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Suprime notificaciones para trabajadores específicos creando registros de confirmación.
    Esto evita que se envíen notificaciones futuras.
    """
    verify_admin_permissions(current_user)
    
    stats = {
        "total_requested": len(request.worker_ids),
        "suppressions_created": 0,
        "already_suppressed": 0,
        "details": []
    }
    
    notification_types = [request.notification_type.value] if request.notification_type else [
        "first_notification", "reminder", "overdue"
    ]
    
    for worker_id in request.worker_ids:
        try:
            worker = db.query(Worker).filter(Worker.id == worker_id).first()
            if not worker:
                stats["details"].append({
                    "worker_id": worker_id,
                    "status": "error",
                    "message": "Trabajador no encontrado"
                })
                continue
            
            # Obtener el último examen del trabajador
            latest_exam = db.query(OccupationalExam).filter(
                OccupationalExam.worker_id == worker_id
            ).order_by(OccupationalExam.exam_date.desc()).first()
            
            if not latest_exam:
                stats["details"].append({
                    "worker_id": worker_id,
                    "worker_name": worker.full_name,
                    "status": "error",
                    "message": "No se encontraron exámenes para este trabajador"
                })
                continue
            
            suppressions_for_worker = 0
            
            for notification_type in notification_types:
                # Verificar si ya existe una supresión
                existing_ack = db.query(NotificationAcknowledgment).filter(
                    and_(
                        NotificationAcknowledgment.worker_id == worker_id,
                        NotificationAcknowledgment.occupational_exam_id == latest_exam.id,
                        NotificationAcknowledgment.notification_type == notification_type,
                        NotificationAcknowledgment.stops_notifications == True
                    )
                ).first()
                
                if existing_ack:
                    stats["already_suppressed"] += 1
                else:
                    # Crear registro de supresión
                    acknowledgment = NotificationAcknowledgment(
                        worker_id=worker_id,
                        occupational_exam_id=latest_exam.id,
                        notification_type=notification_type,
                        ip_address="admin_suppression",
                        user_agent=f"Admin: {current_user.email} - Reason: {request.reason or 'Manual suppression'}",
                        stops_notifications=True
                    )
                    
                    db.add(acknowledgment)
                    suppressions_for_worker += 1
            
            if suppressions_for_worker > 0:
                stats["suppressions_created"] += suppressions_for_worker
                stats["details"].append({
                    "worker_id": worker_id,
                    "worker_name": worker.full_name,
                    "status": "suppressed",
                    "message": f"Suprimidas {suppressions_for_worker} notificaciones",
                    "notification_types": notification_types
                })
            else:
                stats["details"].append({
                    "worker_id": worker_id,
                    "worker_name": worker.full_name,
                    "status": "already_suppressed",
                    "message": "Todas las notificaciones ya estaban suprimidas"
                })
                
        except Exception as e:
            stats["details"].append({
                "worker_id": worker_id,
                "status": "error",
                "message": f"Error procesando trabajador: {str(e)}"
            })
    
    db.commit()
    return NotificationSuppressionResponse(**stats)


@router.get("/acknowledgments", response_model=List[NotificationAcknowledgmentResponse])
async def get_notification_acknowledgments(
    worker_id: Optional[int] = Query(None),
    notification_type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Obtiene la lista de confirmaciones de notificaciones.
    """
    verify_admin_permissions(current_user)
    
    query = (
        db.query(NotificationAcknowledgment, Worker.full_name)
        .join(Worker, NotificationAcknowledgment.worker_id == Worker.id)
        .order_by(desc(NotificationAcknowledgment.acknowledged_at))
    )
    
    if worker_id:
        query = query.filter(NotificationAcknowledgment.worker_id == worker_id)
    
    if notification_type:
        query = query.filter(NotificationAcknowledgment.notification_type == notification_type)
    
    results = query.offset(skip).limit(limit).all()
    
    return [
        NotificationAcknowledgmentResponse(
            id=ack.id,
            worker_id=ack.worker_id,
            worker_name=worker_name,
            occupational_exam_id=ack.occupational_exam_id,
            notification_type=ack.notification_type,
            acknowledged_at=ack.acknowledged_at,
            ip_address=ack.ip_address,
            user_agent=ack.user_agent,
            stops_notifications=ack.stops_notifications
        )
        for ack, worker_name in results
    ]


@router.get("/statistics", response_model=NotificationStatistics)
async def get_notification_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Obtiene estadísticas generales de notificaciones de exámenes ocupacionales.
    """
    verify_admin_permissions(current_user)
    
    service = OccupationalExamNotificationService(db)
    today = date.today()
    
    # Estadísticas básicas
    total_workers = db.query(Worker).filter(Worker.is_active == True).count()
    
    # Trabajadores sin exámenes
    workers_without_exams = (
        db.query(Worker)
        .outerjoin(OccupationalExam)
        .filter(
            and_(
                Worker.is_active == True,
                OccupationalExam.id.is_(None)
            )
        )
        .count()
    )
    
    # Trabajadores con exámenes vencidos (aproximación)
    workers_with_overdue = len([
        w for w in service.get_workers_with_pending_exams(days_ahead=0)
        if w["status"] == "vencido"
    ])
    
    # Trabajadores con exámenes próximos a vencer
    workers_with_upcoming = len([
        w for w in service.get_workers_with_pending_exams(days_ahead=30)
        if w["status"] == "proximo_a_vencer"
    ])
    
    # Confirmaciones de hoy
    acknowledgments_today = (
        db.query(NotificationAcknowledgment)
        .filter(func.date(NotificationAcknowledgment.acknowledged_at) == today)
        .count()
    )
    
    # Notificaciones suprimidas (confirmaciones que detienen notificaciones)
    suppressed_notifications = (
        db.query(NotificationAcknowledgment)
        .filter(NotificationAcknowledgment.stops_notifications == True)
        .count()
    )
    
    return NotificationStatistics(
        total_workers=total_workers,
        workers_without_exams=workers_without_exams,
        workers_with_overdue_exams=workers_with_overdue,
        workers_with_upcoming_exams=workers_with_upcoming,
        total_notifications_sent_today=0,  # Esto requeriría un log de envíos
        total_acknowledgments_today=acknowledgments_today,
        suppressed_notifications=suppressed_notifications
    )


@router.delete("/acknowledgments/{acknowledgment_id}", response_model=MessageResponse)
async def delete_acknowledgment(
    acknowledgment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Elimina una confirmación de notificación, permitiendo que se envíen notificaciones nuevamente.
    """
    verify_admin_permissions(current_user)
    
    acknowledgment = db.query(NotificationAcknowledgment).filter(
        NotificationAcknowledgment.id == acknowledgment_id
    ).first()
    
    if not acknowledgment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Confirmación no encontrada"
        )
    
    worker = db.query(Worker).filter(Worker.id == acknowledgment.worker_id).first()
    worker_name = worker.full_name if worker else "Desconocido"
    
    db.delete(acknowledgment)
    db.commit()
    
    return MessageResponse(
        message=f"Confirmación eliminada exitosamente para {worker_name}. Las notificaciones pueden enviarse nuevamente.",
        success=True
    )


@router.post("/bulk-action", response_model=BulkNotificationResponse)
async def bulk_notification_action(
    action: BulkNotificationAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Ejecuta acciones en lote sobre notificaciones.
    """
    verify_admin_permissions(current_user)
    
    if action.action == "send":
        if not action.notification_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="notification_type es requerido para la acción 'send'"
            )
        
        send_request = NotificationSendRequest(
            worker_ids=action.worker_ids,
            notification_type=action.notification_type,
            force_send=action.force
        )
        
        result = await send_notifications(send_request, db, current_user)
        
        return BulkNotificationResponse(
            action=action.action,
            total_requested=result.total_requested,
            successful=result.emails_sent,
            failed=result.emails_failed,
            skipped=result.already_acknowledged + result.invalid_workers,
            details=result.details
        )
    
    elif action.action == "suppress":
        suppress_request = NotificationSuppressionRequest(
            worker_ids=action.worker_ids,
            notification_type=action.notification_type,
            reason=action.reason
        )
        
        result = await suppress_notifications(suppress_request, db, current_user)
        
        return BulkNotificationResponse(
            action=action.action,
            total_requested=result.total_requested,
            successful=result.suppressions_created,
            failed=0,
            skipped=result.already_suppressed,
            details=result.details
        )
    
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Acción '{action.action}' no soportada"
        )