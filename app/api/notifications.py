from typing import Any, List
from datetime import datetime, date
import json
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.dependencies import get_current_active_user
from app.database import get_db
from app.models.user import User
from app.models.worker import Worker
from app.models.occupational_exam import OccupationalExam
from app.models.notification import Notification, NotificationTemplate, NotificationType, NotificationStatus, NotificationPriority
from app.schemas.notification import (
    NotificationCreate, NotificationUpdate, NotificationResponse,
    NotificationListResponse, NotificationTemplateCreate, NotificationTemplateUpdate,
    NotificationTemplateResponse, BulkNotificationCreate, NotificationPreferences
)
from app.schemas.common import MessageResponse, PaginatedResponse
from app.config import settings

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[NotificationListResponse])
async def get_notifications(
    skip: int = 0,
    limit: int = 100,
    notification_type: NotificationType = None,
    status: NotificationStatus = None,
    priority: NotificationPriority = None,
    unread_only: bool = False,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get notifications for current user (or all notifications if admin)
    """
    # Admin users can see all notifications, regular users only see their own
    if current_user.role == "admin":
        query = db.query(Notification)
    else:
        query = db.query(Notification).filter(Notification.user_id == current_user.id)
    
    # Apply filters
    if notification_type:
        query = query.filter(Notification.notification_type == notification_type)
    
    if status:
        query = query.filter(Notification.status == status)
    
    if priority:
        query = query.filter(Notification.priority == priority)
    
    if unread_only:
        query = query.filter(Notification.read_at.is_(None))
    
    # Order by creation date (newest first)
    query = query.order_by(Notification.created_at.desc())
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    notifications = query.offset(skip).limit(limit).all()
    
    # Calculate pagination info
    page = (skip // limit) + 1 if limit > 0 else 1
    pages = (total + limit - 1) // limit if limit > 0 else 1
    has_next = skip + limit < total
    has_prev = skip > 0
    
    return PaginatedResponse(
        items=notifications,
        total=total,
        page=page,
        size=limit,
        pages=pages,
        has_next=has_next,
        has_prev=has_prev
    )


@router.post("/", response_model=NotificationResponse)
async def create_notification(
    notification_data: NotificationCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Create new notification (admin only)
    """
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes"
        )
    
    # Check if user exists
    user = db.query(User).filter(User.id == notification_data.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    # Create new notification
    notification = Notification(
        **notification_data.dict()
    )
    
    db.add(notification)
    db.commit()
    db.refresh(notification)
    
    # If notification type is EMAIL, send email automatically
    if notification.notification_type == NotificationType.EMAIL and user.email:
        from app.utils.email import send_email
        
        background_tasks.add_task(
            send_email,
            recipient=user.email,
            subject=notification.title,
            body=notification.message,
            template="notification",
            context={
                "user_name": f"{user.first_name} {user.last_name}",
                "title": notification.title,
                "message": notification.message,
                "notification_type": notification.notification_type.value,
                "priority": notification.priority.value,
                "created_at": notification.created_at.strftime('%d/%m/%Y %H:%M'),
                "system_url": settings.react_app_api_url
            }
        )
        
        # Update notification status to SENT
        notification.status = NotificationStatus.SENT
        notification.sent_at = datetime.now()
        db.commit()
        db.refresh(notification)
    
    return notification


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get notification by ID
    """
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notificación no encontrada"
        )
    
    # Users can only see their own notifications unless they are admin
    if current_user.role.value != "admin" and notification.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes"
        )
    
    return notification


@router.put("/{notification_id}", response_model=NotificationResponse)
async def update_notification(
    notification_id: int,
    notification_data: NotificationUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Update notification (admin only)
    """
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes"
        )
    
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notificación no encontrada"
        )
    
    # Update notification fields
    update_data = notification_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(notification, field, value)
    
    db.commit()
    db.refresh(notification)
    
    return notification


@router.delete("/{notification_id}", response_model=MessageResponse)
async def delete_notification(
    notification_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Delete notification
    """
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notificación no encontrada"
        )
    
    # Users can only delete their own notifications unless they are admin
    if current_user.role.value != "admin" and notification.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes"
        )
    
    db.delete(notification)
    db.commit()
    
    return MessageResponse(message="Notificación eliminada exitosamente")


@router.post("/{notification_id}/mark-read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    # Buscar la notificación en la base de datos
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    # Verificar que la notificación pertenece al usuario actual o es admin
    if current_user.role.value != "admin" and notification.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes"
        )
    
    # Marcar como leída
    notification.read_at = datetime.now()
    db.commit()
    db.refresh(notification)
    
    return notification


@router.post("/send-exam-notification/{worker_id}/{exam_id}", status_code=status.HTTP_200_OK)
async def send_exam_notification(
    worker_id: int,
    exam_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Envía una notificación por correo electrónico al trabajador sobre un examen ocupacional vencido o próximo a vencer.
    Solo administradores pueden enviar estas notificaciones.
    """
    # Verificar permisos (solo admin)
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para enviar notificaciones"
        )
    
    # Obtener el trabajador
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trabajador con ID {worker_id} no encontrado"
        )
    
    # Obtener el examen
    exam = db.query(OccupationalExam).filter(OccupationalExam.id == exam_id).first()
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Examen con ID {exam_id} no encontrado"
        )
    
    # Verificar que el examen pertenece al trabajador
    if exam.worker_id != worker_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El examen no pertenece al trabajador especificado"
        )
    
    # Verificar que el trabajador tiene correo electrónico
    if not worker.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El trabajador no tiene correo electrónico registrado"
        )
    
    # Calcular si está vencido
    from datetime import date
    from dateutil.relativedelta import relativedelta
    from sqlalchemy import and_
    from app.models.admin_config import AdminConfig
    from app.models.occupational_exam import ExamType
    
    today = date.today()
    next_exam_date = exam.exam_date
    
    # Get position configuration to determine periodicity
    position_config = db.query(AdminConfig).filter(
        and_(
            AdminConfig.category == "position",
            AdminConfig.display_name == worker.position,
            AdminConfig.is_active == True
        )
    ).first()
    
    periodicity = position_config.emo_periodicity if position_config else None
    
    # Calcular próxima fecha según periodicidad
    if periodicity and (exam.exam_type == ExamType.PERIODICO or exam.exam_type == ExamType.INGRESO):
        if periodicity == "anual":
            # Add exactly one year to the exam date
            try:
                next_exam_date = exam.exam_date.replace(year=exam.exam_date.year + 1)
            except ValueError:
                # Handle leap year edge case (Feb 29)
                next_exam_date = exam.exam_date.replace(year=exam.exam_date.year + 1, month=2, day=28)
        elif periodicity == "semestral":
            # Add 6 months
            month = exam.exam_date.month + 6
            year = exam.exam_date.year
            if month > 12:
                month -= 12
                year += 1
            try:
                next_exam_date = date(year, month, exam.exam_date.day)
            except ValueError:
                # Handle month with fewer days
                import calendar
                last_day = calendar.monthrange(year, month)[1]
                next_exam_date = date(year, month, min(exam.exam_date.day, last_day))
        elif periodicity == "trimestral":
            # Add 3 months
            month = exam.exam_date.month + 3
            year = exam.exam_date.year
            if month > 12:
                month -= 12
                year += 1
            try:
                next_exam_date = date(year, month, exam.exam_date.day)
            except ValueError:
                # Handle month with fewer days
                import calendar
                last_day = calendar.monthrange(year, month)[1]
                next_exam_date = date(year, month, min(exam.exam_date.day, last_day))
    
    is_overdue = next_exam_date < today
    days_until_next = (next_exam_date - today).days
    
    # Crear notificación
    notification_title = "Examen Ocupacional Próximo" if not is_overdue else "Examen Ocupacional Vencido"
    notification_message = f"Su examen ocupacional {'está vencido' if is_overdue else 'vence pronto'}. Fecha programada: {next_exam_date.strftime('%d/%m/%Y')}"
    
    # Enviar correo en segundo plano
    from app.utils.email import send_email
    background_tasks.add_task(
        send_email,
        recipient=worker.email,
        subject=notification_title,
        template="exam_notification",
        context={
            "worker_name": worker.full_name,
            "exam_type": exam.exam_type.value,
            "exam_date": next_exam_date.strftime('%d/%m/%Y'),
            "is_overdue": is_overdue,
            "current_year": today.year,
            "company_name": "Sistema de Gestión SST"
        }
    )
    
    # Crear notificación en la base de datos (tipo EMAIL)
    notification = Notification(
        user_id=worker.user_id,
        title=notification_title,
        message=notification_message,
        notification_type=NotificationType.EMAIL,
        priority=NotificationPriority.HIGH if is_overdue else NotificationPriority.NORMAL,
        additional_data=json.dumps({
            'exam_id': exam.id,
            'worker_id': worker.id,
            'next_exam_date': next_exam_date.isoformat()
        })
    )
    db.add(notification)
    db.commit()
    
    return {"message": f"Notificación enviada al correo {worker.email}"}
    """
    Mark notification as read
    """
    notification = db.query(Notification).filter(
        and_(
            Notification.id == notification_id,
            Notification.user_id == current_user.id
        )
    ).first()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    notification.status = NotificationStatus.READ
    notification.read_at = datetime.now()
    
    db.commit()
    db.refresh(notification)
    
    return notification


@router.post("/mark-all-read", response_model=MessageResponse)
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Mark all notifications as read for current user
    """
    notifications = db.query(Notification).filter(
        and_(
            Notification.user_id == current_user.id,
            Notification.read_at.is_(None)
        )
    ).all()

    for notification in notifications:
        notification.read_at = datetime.now()

    db.commit()

    return MessageResponse(message=f"Se marcaron {len(notifications)} notificaciones como leídas")


@router.post("/{notification_id}/send", response_model=MessageResponse)
async def send_notification(
    notification_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Send a notification via email
    """
    # Get the notification
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    # Check permissions - users can only send their own notifications unless they are admin
    if current_user.role.value != "admin" and notification.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes"
        )
    
    # Get the user to send the email to
    user = db.query(User).filter(User.id == notification.user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    if not user.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario no tiene dirección de correo electrónico"
        )
    
    # Send email in background
    from app.utils.email import send_email
    
    background_tasks.add_task(
        send_email,
        recipient=user.email,
        subject=notification.title,
        body=notification.message,
        template="notification",
        context={
            "user_name": f"{user.first_name} {user.last_name}",
            "title": notification.title,
            "message": notification.message,
            "notification_type": notification.notification_type.value,
            "priority": notification.priority.value,
            "created_at": notification.created_at.strftime('%d/%m/%Y %H:%M'),
            "system_url": settings.react_app_api_url
        }
    )
    
    # Update notification status to SENT
    notification.status = NotificationStatus.SENT
    notification.sent_at = datetime.now()
    
    db.commit()
    
    return MessageResponse(message=f"Notificación enviada a {user.email}")


@router.get("/unread/count")
async def get_unread_count(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get count of unread notifications for current user
    """
    count = db.query(Notification).filter(
        and_(
            Notification.user_id == current_user.id,
            Notification.read_at.is_(None)
        )
    ).count()
    
    return {"unread_count": count}


# Bulk notifications
@router.post("/bulk", response_model=MessageResponse)
async def create_bulk_notifications(
    bulk_data: BulkNotificationCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Create bulk notifications (admin only)
    
    Puede enviar notificaciones a:
    - Usuarios específicos (user_ids)
    - Usuarios por roles (user_roles: admin, trainer, employee, supervisor)
    - Todos los usuarios (si no se especifica user_ids ni user_roles)
    """
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes"
        )
    
    # Determine target users based on input
    if bulk_data.user_ids:
        # Send to specific user IDs
        existing_users = db.query(User.id).filter(User.id.in_(bulk_data.user_ids)).all()
        existing_user_ids = [user.id for user in existing_users]
        
        if len(existing_user_ids) != len(bulk_data.user_ids):
            missing_ids = set(bulk_data.user_ids) - set(existing_user_ids)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Usuarios no encontrados: {list(missing_ids)}"
            )
        
        target_user_ids = bulk_data.user_ids
    elif bulk_data.user_roles:
        # Send to users with specific roles
        from app.models.user import UserRole
        
        # Validate roles
        valid_roles = [role.value for role in UserRole]
        invalid_roles = [role for role in bulk_data.user_roles if role not in valid_roles]
        
        if invalid_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Roles inválidos: {invalid_roles}. Los roles válidos son: {valid_roles}"
            )
        
        # Get users with specified roles
        users_by_role = db.query(User.id).filter(User.role.in_(bulk_data.user_roles)).all()
        target_user_ids = [user.id for user in users_by_role]
        
        if not target_user_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontraron usuarios con los roles: {bulk_data.user_roles}"
            )
    else:
        # Send to all users
        all_users = db.query(User.id).all()
        target_user_ids = [user.id for user in all_users]
    
    # Create notifications for all target users
    notifications = []
    for user_id in target_user_ids:
        notification = Notification(
            user_id=user_id,
            title=bulk_data.title,
            message=bulk_data.message,
            notification_type=bulk_data.notification_type,
            priority=bulk_data.priority
        )
        notifications.append(notification)
    
    db.add_all(notifications)
    db.commit()
    
    # If notification type is EMAIL, send emails automatically
    if bulk_data.notification_type == NotificationType.EMAIL:
        from app.utils.email import send_email
        
        # Get users with emails for sending
        users_with_emails = db.query(User).filter(
            and_(
                User.id.in_(target_user_ids),
                User.email.isnot(None),
                User.email != ""
            )
        ).all()
        
        # Send emails and update notification status
        for user in users_with_emails:
            # Find the corresponding notification
            notification = next((n for n in notifications if n.user_id == user.id), None)
            if notification:
                background_tasks.add_task(
                    send_email,
                    recipient=user.email,
                    subject=bulk_data.title,
                    body=bulk_data.message,
                    template="notification",
                    context={
                        "user_name": f"{user.first_name} {user.last_name}",
                        "title": bulk_data.title,
                        "message": bulk_data.message,
                        "notification_type": bulk_data.notification_type.value,
                        "priority": bulk_data.priority.value,
                        "created_at": notification.created_at.strftime('%d/%m/%Y %H:%M'),
                        "system_url": settings.react_app_api_url
                    }
                )
                
                # Update notification status to SENT
                notification.status = NotificationStatus.SENT
                notification.sent_at = datetime.now()
        
        db.commit()
        
        return MessageResponse(message=f"Se crearon {len(notifications)} notificaciones, {len(users_with_emails)} correos enviados")
    
    return MessageResponse(message=f"Se crearon {len(notifications)} notificaciones")


@router.post("/send-by-role", response_model=MessageResponse)
async def send_notifications_by_role(
    roles: list[str],
    title: str,
    message: str,
    notification_type: NotificationType = NotificationType.IN_APP,
    priority: NotificationPriority = NotificationPriority.NORMAL,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Enviar notificaciones a usuarios por roles específicos
    
    Roles disponibles: admin, trainer, employee, supervisor
    """
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes"
        )
    
    from app.models.user import UserRole
    
    # Validate roles
    valid_roles = [role.value for role in UserRole]
    invalid_roles = [role for role in roles if role not in valid_roles]
    
    if invalid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Roles inválidos: {invalid_roles}. Los roles válidos son: {valid_roles}"
        )
    
    # Get users with specified roles
    users_by_role = db.query(User).filter(User.role.in_(roles), User.is_active == True).all()
    
    if not users_by_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontraron usuarios activos con los roles: {roles}"
        )
    
    # Create notifications for all target users
    notifications = []
    for user in users_by_role:
        notification = Notification(
            user_id=user.id,
            title=title,
            message=message,
            notification_type=notification_type,
            priority=priority
        )
        notifications.append(notification)
    
    db.add_all(notifications)
    db.commit()
    
    return MessageResponse(
        message=f"Se enviaron {len(notifications)} notificaciones a usuarios con roles: {', '.join(roles)}"
    )


@router.post("/send-to-all", response_model=MessageResponse)
async def send_notifications_to_all(
    title: str,
    message: str,
    notification_type: NotificationType = NotificationType.IN_APP,
    priority: NotificationPriority = NotificationPriority.NORMAL,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Enviar notificaciones a todos los usuarios activos del sistema
    """
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes"
        )
    
    # Get all active users
    all_users = db.query(User).filter(User.is_active == True).all()
    
    if not all_users:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontraron usuarios activos"
        )
    
    # Create notifications for all users
    notifications = []
    for user in all_users:
        notification = Notification(
            user_id=user.id,
            title=title,
            message=message,
            notification_type=notification_type,
            priority=priority
        )
        notifications.append(notification)
    
    db.add_all(notifications)
    db.commit()
    
    return MessageResponse(
        message=f"Se enviaron {len(notifications)} notificaciones a todos los usuarios activos"
    )


# Notification Templates
@router.get("/templates", response_model=PaginatedResponse[NotificationTemplateResponse])
async def get_notification_templates(
    skip: int = 0,
    limit: int = 100,
    notification_type: NotificationType = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get notification templates (admin only)
    """
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    query = db.query(NotificationTemplate)
    
    if notification_type:
        query = query.filter(NotificationTemplate.notification_type == notification_type)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    templates = query.offset(skip).limit(limit).all()
    
    # Calculate pagination info
    page = (skip // limit) + 1 if limit > 0 else 1
    pages = (total + limit - 1) // limit if limit > 0 else 1
    has_next = skip + limit < total
    has_prev = skip > 0
    
    return PaginatedResponse(
        items=templates,
        total=total,
        page=page,
        size=limit,
        pages=pages,
        has_next=has_next,
        has_prev=has_prev
    )


@router.post("/templates", response_model=NotificationTemplateResponse)
async def create_notification_template(
    template_data: NotificationTemplateCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Create notification template (admin only)
    """
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Check if template with same name already exists
    existing_template = db.query(NotificationTemplate).filter(
        NotificationTemplate.name == template_data.name
    ).first()
    
    if existing_template:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una plantilla con este nombre"
        )
    
    # Create new template
    template = NotificationTemplate(
        **template_data.dict()
    )
    
    db.add(template)
    db.commit()
    db.refresh(template)
    
    return template


@router.get("/templates/{template_id}", response_model=NotificationTemplateResponse)
async def get_notification_template(
    template_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get notification template by ID (admin only)
    """
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    template = db.query(NotificationTemplate).filter(NotificationTemplate.id == template_id).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plantilla no encontrada"
        )
    
    return template


@router.put("/templates/{template_id}", response_model=NotificationTemplateResponse)
async def update_notification_template(
    template_id: int,
    template_data: NotificationTemplateUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Update notification template (admin only)
    """
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    template = db.query(NotificationTemplate).filter(NotificationTemplate.id == template_id).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plantilla no encontrada"
        )
    
    # Update template fields
    update_data = template_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)
    
    db.commit()
    db.refresh(template)
    
    return template


@router.delete("/templates/{template_id}", response_model=MessageResponse)
async def delete_notification_template(
    template_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Delete notification template (admin only)
    """
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    template = db.query(NotificationTemplate).filter(NotificationTemplate.id == template_id).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    db.delete(template)
    db.commit()
    
    return MessageResponse(message="Plantilla eliminada exitosamente")


@router.post("/templates/{template_id}/send", response_model=MessageResponse)
async def send_notification_from_template(
    template_id: int,
    user_ids: List[int],
    variables: dict = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Send notifications using a template (admin only)
    """
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Get template
    template = db.query(NotificationTemplate).filter(NotificationTemplate.id == template_id).first()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    # Validate user IDs
    existing_users = db.query(User.id).filter(User.id.in_(user_ids)).all()
    existing_user_ids = [user.id for user in existing_users]
    
    if len(existing_user_ids) != len(user_ids):
        missing_ids = set(user_ids) - set(existing_user_ids)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Usuarios no encontrados: {list(missing_ids)}"
        )
    
    # Process template variables
    title = template.title_template
    message = template.message_template
    
    if variables:
        for key, value in variables.items():
            title = title.replace(f"{{{key}}}", str(value))
            message = message.replace(f"{{{key}}}", str(value))
    
    # Create notifications
    notifications = []
    for user_id in user_ids:
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=template.notification_type,
            priority=template.priority
        )
        notifications.append(notification)
    
    db.add_all(notifications)
    db.commit()
    
    return MessageResponse(message=f"Se enviaron {len(notifications)} notificaciones usando la plantilla")


# User preferences
@router.get("/preferences", response_model=NotificationPreferences)
async def get_notification_preferences(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get notification preferences for current user
    """
    # This would typically be stored in a separate preferences table
    # For now, return default preferences
    return NotificationPreferences(
        email_notifications=True,
        push_notifications=True,
        sms_notifications=False,
        notification_types={
            "course": True,
            "evaluation": True,
            "certificate": True,
            "system": True,
            "reminder": True
        }
    )


@router.put("/preferences", response_model=NotificationPreferences)
async def update_notification_preferences(
    preferences: NotificationPreferences,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Update notification preferences for current user
    """
    # Update user preferences logic here
    return preferences


@router.post("/send-test-email", response_model=MessageResponse)
async def send_test_email(
    recipient_email: str,
    title: str = "Email de Prueba - Sistema SST",
    message: str = "Este es un email de prueba del sistema de notificaciones SST.",
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Send test email to any email address (admin only)
    """
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    from app.utils.email import send_email
    
    try:
        background_tasks.add_task(
            send_email,
            recipient=recipient_email,
            subject=title,
            body=message,
            template="notification",
            context={
                "user_name": "Usuario de Prueba",
                "title": title,
                "message": message,
                "notification_type": "email",
                "priority": "normal",
                "created_at": datetime.now().strftime('%d/%m/%Y %H:%M'),
                "system_url": settings.react_app_api_url
            }
        )
        
        return {
            "success": True,
            "message": f"Email de prueba enviado exitosamente a {recipient_email}"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al enviar correo electrónico: {str(e)}"
        )
    
    # For now, just return the provided preferences
    return preferences