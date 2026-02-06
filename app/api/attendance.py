from typing import Any, Optional
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo
import uuid
import secrets
import string
from fastapi import APIRouter, Depends, HTTPException, status, Response, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
import os
import tempfile
import io
import pandas as pd
from starlette.background import BackgroundTask

from app.dependencies import get_current_active_user
from app.database import get_db
from app.models.user import User
from app.models.worker import Worker
from app.models.attendance import Attendance, AttendanceStatus, AttendanceType, VirtualSession
from app.models.course import Course
from app.models.session import Session as SessionModel
from app.models.certificate import Certificate, CertificateStatus
from app.services.certificate_generator import CertificateGenerator
from app.services.html_to_pdf import HTMLToPDFConverter
from app.schemas.attendance import (
    AttendanceUpdate,
    AttendanceResponse,
    AttendanceListResponse,
    AttendanceSummary,
    BulkAttendanceCreate,
    BulkAttendanceResponse,
    AttendanceNotificationData,
    VirtualAttendanceCheckIn,
    VirtualAttendanceCheckOut,
    SessionCodeGenerate,
    SessionCodeValidate,
    VirtualAttendanceResponse,
)
from app.schemas.certificate import CertificateResponse
from app.schemas.session import (
    SessionCreate,
    SessionUpdate,
    SessionResponse,
    SessionListResponse,
)
from app.schemas.common import MessageResponse, PaginatedResponse
from app.models.notification import Notification, NotificationType, NotificationPriority
from app.models.enrollment import Enrollment
from pydantic import BaseModel

router = APIRouter()


class CertificateRequest(BaseModel):
    course_id: Optional[int] = None


# Session endpoints (must be before generic /{attendance_id} routes)
@router.get("/sessions", response_model=PaginatedResponse[SessionListResponse])
async def get_sessions(
    skip: int = 0,
    limit: int = 100,
    # course_id: int = None,
    is_active: bool = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get sessions with optional filtering
    """
    query = db.query(SessionModel)

    # if course_id:
    #     query = query.filter(SessionModel.course_id == course_id)

    if is_active is not None:
        query = query.filter(SessionModel.is_active == is_active)

    # Order by session date and start time
    query = query.order_by(
        SessionModel.session_date.desc(), SessionModel.start_time.desc()
    )

    total = query.count()
    sessions = query.offset(skip).limit(limit).all()

    # Manually construct response data for each session
    sessions_data = []
    for session in sessions:
        # Get course information for each session
        course = db.query(Course).filter(Course.id == session.course_id).first()

        session_data = {
            "id": session.id,
            "course_id": session.course_id,
            "title": session.title,
            "session_date": session.session_date,
            "start_time": session.start_time,
            "end_time": session.end_time,
            "location": session.location,
            "is_active": session.is_active,
            "duration_minutes": session.duration_minutes,
            "attendance_count": session.attendance_count,
            "course": (
                {
                    "id": course.id,
                    "title": course.title,
                    "type": course.course_type.value if course.course_type else None,
                }
                if course
                else None
            ),
        }
        sessions_data.append(session_data)

    # Calculate pagination info
    page = (skip // limit) + 1 if limit > 0 else 1
    pages = (total + limit - 1) // limit if limit > 0 else 1
    has_next = skip + limit < total
    has_prev = skip > 0

    return PaginatedResponse(
        items=sessions_data,
        total=total,
        page=page,
        size=limit,
        pages=pages,
        has_next=has_next,
        has_prev=has_prev,
    )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get session by ID
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sesión no encontrada"
        )

    # Get course information for response
    course = db.query(Course).filter(Course.id == session.course_id).first()

    # Manually construct response with course as dictionary
    response_data = {
        "id": session.id,
        "course_id": session.course_id,
        "title": session.title,
        "description": session.description,
        "session_date": session.session_date,
        "start_time": session.start_time,
        "end_time": session.end_time,
        "location": session.location,
        "max_capacity": session.max_capacity,
        "is_active": session.is_active,
        "duration_minutes": session.duration_minutes,
        "is_past": session.is_past,
        "is_current": session.is_current,
        "attendance_count": session.attendance_count,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "course": (
            {
                "id": course.id,
                "title": course.title,
                "type": course.course_type.value if course.course_type else None,
            }
            if course
            else None
        ),
    }

    return response_data


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    session_data: SessionCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Create new session (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "trainer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficientes"
        )

    # Check if course exists
    course = db.query(Course).filter(Course.id == session_data.course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Curso no encontrado"
        )

    session = SessionModel(**session_data.dict())
    db.add(session)
    db.commit()
    db.refresh(session)

    # Manually construct response with course as dictionary
    response_data = {
        "id": session.id,
        "course_id": session.course_id,
        "title": session.title,
        "description": session.description,
        "session_date": session.session_date,
        "start_time": session.start_time,
        "end_time": session.end_time,
        "location": session.location,
        "max_capacity": session.max_capacity,
        "is_active": session.is_active,
        "duration_minutes": session.duration_minutes,
        "is_past": session.is_past,
        "is_current": session.is_current,
        "attendance_count": session.attendance_count,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "course": {
            "id": course.id,
            "title": course.title,
            "type": course.course_type.value if course.course_type else None,
        },
    }

    return response_data


@router.put("/sessions/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: int,
    session_data: SessionUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update session (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "trainer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficientes"
        )

    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sesión no encontrada"
        )

    # Update session fields
    update_data = session_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(session, field, value)

    db.commit()
    db.refresh(session)

    # Get course information for response
    course = db.query(Course).filter(Course.id == session.course_id).first()

    # Manually construct response with course as dictionary
    response_data = {
        "id": session.id,
        "course_id": session.course_id,
        "title": session.title,
        "description": session.description,
        "session_date": session.session_date,
        "start_time": session.start_time,
        "end_time": session.end_time,
        "location": session.location,
        "max_capacity": session.max_capacity,
        "is_active": session.is_active,
        "duration_minutes": session.duration_minutes,
        "is_past": session.is_past,
        "is_current": session.is_current,
        "attendance_count": session.attendance_count,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "course": (
            {
                "id": course.id,
                "title": course.title,
                "type": course.course_type.value if course.course_type else None,
            }
            if course
            else None
        ),
    }

    return response_data


@router.delete("/sessions/{session_id}", response_model=MessageResponse)
async def delete_session(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Delete session (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "trainer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficientes"
        )

    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sesión no encontrada"
        )

    db.delete(session)
    db.commit()

    return MessageResponse(message="Sesión eliminada exitosamente")


# Export endpoint (must be before generic /{attendance_id} routes)
@router.get("/export")
async def export_attendance_data(
    session_date: date = None,
    user_id: int = None,
    course_name: str = None,
    status: AttendanceStatus = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Export attendance data to Excel format
    """
    
    # Check permissions
    if current_user.role.value not in ["admin", "trainer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Permisos insuficientes para exportar datos"
        )
    
    # Build query with explicit join conditions to avoid ambiguous foreign keys
    query = db.query(Attendance).join(User, Attendance.user_id == User.id)
    
    # Apply filters
    if user_id:
        query = query.filter(Attendance.user_id == user_id)
    if course_name:
        query = query.filter(Attendance.course_name.ilike(f"%{course_name}%"))
    if session_date:
        query = query.filter(func.date(Attendance.session_date) == session_date)
    if status:
        query = query.filter(Attendance.status == status)
    
    # Get attendance records
    attendance_records = query.all()
    
    # Prepare data for export
    export_data = []
    for record in attendance_records:
        export_data.append({
            'ID': record.id,
            'Usuario': f"{record.user.first_name} {record.user.last_name}",
            'Email': record.user.email,
            'Curso': record.course_name or 'N/A',
            'Fecha de Sesión': record.session_date.strftime('%Y-%m-%d'),
            'Estado': record.status.value,
            'Tipo de Asistencia': record.attendance_type.value,
            'Hora de Entrada': record.check_in_time.strftime('%H:%M:%S') if record.check_in_time else '',
            'Hora de Salida': record.check_out_time.strftime('%H:%M:%S') if record.check_out_time else '',
            'Duración (min)': record.duration_minutes or 0,
            'Porcentaje de Completitud': record.completion_percentage,
            'Ubicación': record.location or '',
            'Notas': record.notes or '',
            'Fecha de Creación': record.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    # Create DataFrame and Excel file
    df = pd.DataFrame(export_data)
    
    # Create Excel file in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Asistencia', index=False)
    
    output.seek(0)
    
    # Generate filename
    filename = f"asistencia_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    return StreamingResponse(
        io.BytesIO(output.read()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# Attendance endpoints
@router.get("", response_model=PaginatedResponse[AttendanceListResponse])
@router.get("/", response_model=PaginatedResponse[AttendanceListResponse])
async def get_attendance_records(
    skip: int = 0,
    limit: int = 100,
    user_id: int = None,
    course_id: int = None,
    session_date: date = None,
    status: AttendanceStatus = None,
    search: str = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get attendance records with optional filtering
    """
    query = db.query(Attendance)

    # Apply search filter by user name
    if search:
        query = query.join(User, Attendance.user_id == User.id).filter(
            User.full_name.ilike(f"%{search}%")
        )

    # Apply filters
    if user_id:
        # Users can only see their own attendance unless they are admin or capacitador
        if (
            current_user.role.value not in ["admin", "trainer"]
            and current_user.id != user_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficientes"
            )
        query = query.filter(Attendance.user_id == user_id)
    elif current_user.role.value not in ["admin", "trainer"]:
        # Non-admin/capacitador users can only see their own attendance
        query = query.filter(Attendance.user_id == current_user.id)

    if session_date:
        query = query.filter(func.date(Attendance.session_date) == session_date)

    if status:
        query = query.filter(Attendance.status == status)

    # Get total count
    total = query.count()

    # Apply pagination and get attendance records
    attendance_records = query.offset(skip).limit(limit).all()

    # Manually construct response data with user and course information
    attendance_data = []
    for record in attendance_records:
        user = db.query(User).filter(User.id == record.user_id).first()
        record_data = {
            "id": record.id,
            "user_id": record.user_id,
            "enrollment_id": record.enrollment_id,
            "session_id": record.session_id,
            "session_date": record.session_date,
            "status": record.status,
            "attendance_type": record.attendance_type,
            "check_in_time": record.check_in_time,
            "check_out_time": record.check_out_time,
            "duration_minutes": record.duration_minutes,
            "scheduled_duration_minutes": record.scheduled_duration_minutes,
            "completion_percentage": record.completion_percentage,
            "location": record.location,
            "ip_address": record.ip_address,
            "device_info": record.device_info,
            "notes": record.notes,
            "verified_by": record.verified_by,
            "verified_at": record.verified_at,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "course_name": getattr(record, "course_name", None),
            "user": (
                {"id": user.id, "name": user.full_name, "email": user.email}
                if user
                else None
            ),
        }
        attendance_data.append(record_data)

    # Calculate pagination info
    page = (skip // limit) + 1 if limit > 0 else 1
    pages = (total + limit - 1) // limit if limit > 0 else 1
    has_next = skip + limit < total
    has_prev = skip > 0

    return PaginatedResponse(
        items=attendance_data,
        total=total,
        page=page,
        size=limit,
        pages=pages,
        has_next=has_next,
        has_prev=has_prev,
    )


@router.post("/", response_model=AttendanceResponse)
async def create_attendance_record(
    attendance_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Crear asistencia independiente del curso (solo guarda el nombre como texto)
    """
    # Validar permisos
    if (
        current_user.role.value not in ["admin", "trainer"]
        and attendance_data.get("user_id") != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    # Verificar duplicados solo por usuario y fecha
    existing_attendance = (
        db.query(Attendance)
        .filter(
            and_(
                Attendance.user_id == attendance_data.get("user_id"),
                func.date(Attendance.session_date)
                == func.date(attendance_data.get("session_date")),
            )
        )
        .first()
    )
    if existing_attendance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Attendance record already exists for this date",
        )

    # Preparar datos para el modelo
    attendance_dict = attendance_data.copy()
    # Guardar el nombre del curso como texto plano
    attendance_dict["course_name"] = attendance_data.get("course_name", "")
    
    # Intentar encontrar enrollment_id basado en user_id y course_name
    if not attendance_dict.get("enrollment_id") and attendance_dict.get("user_id") and attendance_dict.get("course_name"):
        user_id = attendance_dict["user_id"]
        course_name = attendance_dict["course_name"]
        
        # Buscar inscripción que coincida con el nombre del curso
        enrollment = (
            db.query(Enrollment)
            .join(Course)
            .filter(
                Enrollment.user_id == user_id,
                func.lower(Course.title) == func.lower(course_name)
            )
            .first()
        )
        
        # Si no se encuentra coincidencia exacta, buscar coincidencia parcial
        if not enrollment:
            enrollment = (
                db.query(Enrollment)
                .join(Course)
                .filter(
                    Enrollment.user_id == user_id,
                    Course.title.ilike(f"%{course_name}%")
                )
                .order_by(Enrollment.created_at.desc())
                .first()
            )
        
        # Si aún no se encuentra, buscar por palabras clave
        if not enrollment and len(course_name.split()) > 1:
            course_words = [word.strip() for word in course_name.split() if len(word.strip()) > 3]
            for word in course_words:
                enrollment = (
                    db.query(Enrollment)
                    .join(Course)
                    .filter(
                        Enrollment.user_id == user_id,
                        Course.title.ilike(f"%{word}%")
                    )
                    .order_by(Enrollment.created_at.desc())
                    .first()
                )
                if enrollment:
                    break
        
        if enrollment:
            attendance_dict["enrollment_id"] = enrollment.id

    # Calcular duración si aplica
    if attendance_dict.get("check_in_time") and attendance_dict.get("check_out_time"):
        check_in = attendance_dict["check_in_time"]
        check_out = attendance_dict["check_out_time"]
        if isinstance(check_in, str):
            check_in = datetime.fromisoformat(check_in.replace("Z", "+00:00"))
        if isinstance(check_out, str):
            check_out = datetime.fromisoformat(check_out.replace("Z", "+00:00"))
        duration = check_out - check_in
        attendance_dict["duration_minutes"] = int(duration.total_seconds() / 60)
        if not attendance_dict.get("scheduled_duration_minutes"):
            attendance_dict["scheduled_duration_minutes"] = attendance_dict[
                "duration_minutes"
            ]
        if (
            attendance_dict["scheduled_duration_minutes"]
            and attendance_dict["scheduled_duration_minutes"] > 0
        ):
            attendance_dict["completion_percentage"] = min(
                100.0,
                (
                    attendance_dict["duration_minutes"]
                    / attendance_dict["scheduled_duration_minutes"]
                )
                * 100,
            )

    # Remover send_notifications del dict antes de crear el modelo
    send_notifications = attendance_dict.pop("send_notifications", False)
    
    attendance = Attendance(**attendance_dict)
    db.add(attendance)
    db.commit()
    db.refresh(attendance)
    
    # Enviar notificación por email si está habilitado
    if send_notifications:
        try:
            # Obtener información del usuario
            user = db.query(User).filter(User.id == attendance.user_id).first()
            if user and user.email:
                # Preparar datos para la notificación
                notification_data = {
                    "user_name": user.full_name or f"{user.first_name} {user.last_name}",
                    "course_name": attendance.course_name or "Curso",
                    "session_date": attendance.session_date.strftime("%d/%m/%Y"),
                    "status": attendance.status.value,
                    "attendance_type": attendance.attendance_type.value,
                    "location": attendance.location or "No especificada",
                    "notes": attendance.notes or "",
                }
                
                # Enviar email
                from app.utils.email import send_email
                subject = f"Confirmación de Asistencia - {notification_data['course_name']}"
                
                # Template básico para el email
                email_content = f"""
                <h2>Confirmación de Registro de Asistencia</h2>
                <p>Estimado/a {notification_data['user_name']},</p>
                <p>Se ha registrado su asistencia con los siguientes detalles:</p>
                <ul>
                    <li><strong>Curso:</strong> {notification_data['course_name']}</li>
                    <li><strong>Fecha:</strong> {notification_data['session_date']}</li>
                    <li><strong>Estado:</strong> {notification_data['status']}</li>
                    <li><strong>Tipo:</strong> {notification_data['attendance_type']}</li>
                    <li><strong>Ubicación:</strong> {notification_data['location']}</li>
                </ul>
                {f"<p><strong>Notas:</strong> {notification_data['notes']}</p>" if notification_data['notes'] else ""}
                <p>Gracias por su participación.</p>
                """
                
                send_email(
                    recipient=user.email,
                    subject=subject,
                    body=email_content,
                )
                
                # Crear registro de notificación en la base de datos
                from app.models.notification import Notification
                notification = Notification(
                    user_id=user.id,
                    type="attendance_confirmation",
                    title=subject,
                    message=f"Asistencia registrada para {notification_data['course_name']} el {notification_data['session_date']}",
                    is_read=False,
                    email_sent=True,
                    email_sent_at=datetime.utcnow(),
                )
                db.add(notification)
                db.commit()
                
        except Exception as e:
            # Log el error pero no fallar la creación de asistencia
            print(f"Error sending attendance notification: {str(e)}")
    
    return attendance


@router.get("/stats")
async def get_attendance_stats(
    current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
) -> Any:
    """
    Get attendance statistics by status
    """
    # Check permissions
    if current_user.role.value not in ["admin", "trainer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    # Get counts by status
    stats_query = (
        db.query(Attendance.status, func.count(Attendance.id).label("count"))
        .group_by(Attendance.status)
        .all()
    )

    # Initialize stats with default values
    stats = {
        "total_attendance": 0,
        "present": 0,
        "absent": 0,
        "late": 0,
        "excused": 0,
        "partial": 0,
    }

    # Populate stats from query results
    for status_result, count in stats_query:
        if status_result == AttendanceStatus.PRESENT:
            stats["present"] = count
        elif status_result == AttendanceStatus.ABSENT:
            stats["absent"] = count
        elif status_result == AttendanceStatus.LATE:
            stats["late"] = count
        elif status_result == AttendanceStatus.EXCUSED:
            stats["excused"] = count
        elif status_result == AttendanceStatus.PARTIAL:
            stats["partial"] = count

        stats["total_attendance"] += count

    return stats


@router.get("/attendance-list")
async def generate_attendance_list_pdf(
    course_name: str = Query(..., description="Nombre del curso"),
    session_date: str = Query(..., description="Fecha de la sesión (YYYY-MM-DD)"),
    attendance_type: Optional[str] = Query(
        None, description="Tipo de asistencia a filtrar: 'in_person', 'virtual' o None para todos"
    ),
    download: bool = Query(
        False, description="Set to true to download the file with a custom filename"
    ),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Generate attendance list PDF for all participants in a specific course session
    """
    if current_user.role.value not in ["admin", "trainer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    try:
        # Parse session date
        session_date_obj = datetime.strptime(session_date, "%Y-%m-%d").date()

        # Build query with filters
        query = (
            db.query(Attendance)
            .join(User, Attendance.user_id == User.id)
            .filter(
                Attendance.course_name == course_name,
                func.date(Attendance.session_date) == session_date_obj
            )
        )

        # Filtrar por tipo de asistencia si se especifica
        if attendance_type:
            if attendance_type == "in_person":
                query = query.filter(Attendance.attendance_type == AttendanceType.IN_PERSON)
            elif attendance_type == "virtual":
                query = query.filter(Attendance.attendance_type == AttendanceType.VIRTUAL)

        attendances = query.order_by(User.first_name, User.last_name).all()

        if not attendances:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se encontraron registros de asistencia para este curso y fecha",
            )

        # Get course information (try to find from the first attendance record)
        first_attendance = attendances[0]
        course = db.query(Course).filter(Course.title == course_name).first()

        # Determinar etiqueta de tipo de asistencia para el título
        type_label = ""
        if attendance_type == "in_person":
            type_label = " (Presencial)"
        elif attendance_type == "virtual":
            type_label = " (Virtual)"

        # Construir datos de sesión para la plantilla
        session_data = {
            "title": f"Lista de Asistencia{type_label} - {course_name}",
            "session_date": session_date_obj.strftime("%d/%m/%Y"),
            "course_title": course_name,
            "location": course.location if course else "No especificado",
            "duration": f"{first_attendance.duration_minutes or 0} min",
            "attendance_percentage": 100,
        }

        # Construir lista de participantes para la plantilla
        attendees = []
        for attendance in attendances:
            user = attendance.user
            # Buscar el Worker asociado al User para obtener el cargo
            worker = db.query(Worker).filter(Worker.user_id == user.id).first()
            position = ""
            area = ""
            if worker:
                position = worker.position or ""
                # Obtener el área del worker si tiene relación con area_obj
                if worker.area_obj:
                    area = worker.area_obj.name or ""
                else:
                    area = worker.department or ""
            else:
                # Fallback al User si no hay Worker
                position = user.position or ""
                area = user.department or ""

            attendees.append({
                "name": f"{user.first_name} {user.last_name}",
                "document": user.document_number or "",
                "position": position,
                "area": area,
                "signature": "",  # Campo vacío para firma física
            })

        # Preparar datos para el servicio de PDF
        template_data = {"session": session_data, "attendees": attendees}

        # Usar servicio optimizado de PDF
        pdf_service = HTMLToPDFConverter()
        
        # Generar PDF optimizado en memoria primero
        pdf_bytes = pdf_service.generate_attendance_list_pdf(template_data)
        
        # Guardar en archivo temporal solo si es válido
        if not pdf_bytes or len(pdf_bytes) < 1000:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error generando PDF: contenido vacío"
            )
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(pdf_bytes)
            pdf_path = tmp_file.name

        # Validar PDF generado
        is_valid_pdf = False
        if os.path.exists(pdf_path):
            try:
                with open(pdf_path, "rb") as f:
                    header = f.read(4)
                    is_valid_pdf = header == b"%PDF"
            except Exception:
                is_valid_pdf = False

        if not is_valid_pdf:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error generando PDF válido"
            )

        # Nombre de archivo para descarga
        safe_course_name = "".join(c for c in course_name if c.isalnum() or c in "._-")[:20]
        filename = f"lista_asistencia_{safe_course_name}_{session_date}.pdf"
        
        # Configurar respuesta
        response_params = {
            "path": pdf_path,
            "media_type": "application/pdf",
            "background": BackgroundTask(lambda: os.remove(pdf_path)),
        }
        
        if download:
            response_params["filename"] = filename
            
        response = FileResponse(**response_params)
        
        # Agregar headers adicionales para asegurar la descarga
        if download:
            response.headers["Content-Disposition"] = f"attachment; filename={filename}"
            response.headers["Content-Type"] = "application/pdf"
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            
        return response

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato de fecha inválido. Use YYYY-MM-DD"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al generar lista de asistencia: {str(e)}",
        )


@router.get("/courses-for-certificate", response_model=list)
async def get_courses_for_certificate(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Obtener lista de cursos disponibles para asignar a certificados de asistencia.
    Solo permitido para administradores.
    """
    # Validar rol del usuario
    user_role = getattr(current_user, "role", None) or getattr(current_user, "rol", None)
    role_value = user_role.value if hasattr(user_role, "value") else user_role
    if role_value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para acceder a esta información",
        )

    # Obtener todos los cursos activos
    courses = db.query(Course).order_by(Course.title).all()
    
    return [
        {
            "id": course.id,
            "title": course.title,
            "description": course.description,
            "course_type": course.course_type.value if course.course_type else None,
        }
        for course in courses
    ]


# Virtual Session Management Endpoints

@router.post("/virtual-sessions", response_model=dict)
async def create_virtual_session(
    session_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Create a new virtual session (Admin only)
    """
    # Check if user is admin
    if current_user.role not in ["admin", "trainer", "supervisor"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para crear sesiones virtuales"
        )
    
    # Generate a unique session code
    session_code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
    
    # Ensure the session code is unique
    while db.query(VirtualSession).filter(VirtualSession.session_code == session_code).first():
        session_code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
    
    # Helper to normalize any incoming datetime to UTC naive for consistent storage
    def _to_utc_naive(dt: datetime | None) -> datetime | None:
        if dt is None:
            return None
        # If timezone-aware, convert to UTC and drop tzinfo
        if getattr(dt, "tzinfo", None) is not None:
            try:
                return dt.astimezone(timezone.utc).replace(tzinfo=None)
            except Exception:
                pass
        # If string was parsed as naive, assume it's already in desired timezone (backend previously stored naive)
        return dt

    # Parse session_date if it's a string and normalize to UTC naive
    session_date = session_data.get("session_date")
    if isinstance(session_date, str):
        session_date = datetime.fromisoformat(session_date.replace('Z', '+00:00'))
    session_date = _to_utc_naive(session_date)
    
    # Parse end_date if it's a string and normalize to UTC naive
    end_date = session_data.get("end_date")
    if isinstance(end_date, str):
        end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    end_date = _to_utc_naive(end_date)
    if end_date is None:
        # Default to 2 hours after session_date if not provided
        end_date = session_date + timedelta(hours=2)
    
    # Validate that end_date is after session_date
    if end_date <= session_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La fecha de finalización debe ser posterior a la fecha de inicio"
        )
    
    # Set valid_until to end_date (código expira cuando termina la sesión)
    valid_until = end_date
    
    # Create virtual session
    virtual_session = VirtualSession(
        course_name=session_data.get("course_name"),
        session_date=session_date,
        end_date=end_date,
        virtual_session_link=session_data.get("virtual_session_link"),
        session_code=session_code,
        valid_until=valid_until,
        max_participants=session_data.get("max_participants"),
        description=session_data.get("description"),
        created_by=current_user.id,
        is_active=True
    )
    
    db.add(virtual_session)
    db.commit()
    db.refresh(virtual_session)
    
    return {
        "success": True,
        "message": "Sesión virtual creada exitosamente",
        "session_code": session_code,
        "virtual_session": {
            "id": virtual_session.id,
            "course_name": virtual_session.course_name,
            "session_date": virtual_session.session_date,
            "end_date": virtual_session.end_date,
            "virtual_session_link": virtual_session.virtual_session_link,
            "session_code": virtual_session.session_code,
            "valid_until": virtual_session.valid_until,
            "max_participants": virtual_session.max_participants,
            "description": virtual_session.description,
            "is_active": virtual_session.is_active,
            "duration_minutes": virtual_session.duration_minutes
        }
    }


@router.get("/virtual-sessions", response_model=dict)
async def list_virtual_sessions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    List virtual sessions (Admin only)
    """
    # Check if user is admin
    if current_user.role not in ["admin", "trainer", "supervisor"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para ver las sesiones virtuales"
        )
    
    # Get virtual sessions
    virtual_sessions = db.query(VirtualSession).offset(skip).limit(limit).all()
    total = db.query(VirtualSession).count()
    
    # Get participants count for each session
    sessions_data = []
    for session in virtual_sessions:
        participants_count = db.query(Attendance).filter(
            and_(
                Attendance.session_code == session.session_code,
                Attendance.check_in_time.isnot(None)
            )
        ).count()
        
        # Get creator name
        creator = db.query(User).filter(User.id == session.created_by).first()
        creator_name = f"{creator.first_name} {creator.last_name}" if creator else "Desconocido"
        
        sessions_data.append({
            "id": session.id,
            "course_name": session.course_name,
            "session_date": session.session_date,
            "end_date": session.end_date,
            "virtual_session_link": session.virtual_session_link,
            "session_code": session.session_code,
            "valid_until": session.valid_until,
            "max_participants": session.max_participants,
            "description": session.description,
            "is_active": session.is_active,
            "creator_id": session.created_by,
            "creator_name": creator_name,
            "participants_count": participants_count,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "duration_minutes": session.duration_minutes,
            "is_session_active": session.is_session_active,
            "is_session_expired": session.is_session_expired
        })
    
    return {
        "items": sessions_data,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/virtual-sessions/{session_id}/participants", response_model=dict)
async def get_virtual_session_participants(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get real-time participants for a virtual session (Admin only)
    """
    # Check if user is admin
    if current_user.role not in ["admin", "trainer", "supervisor"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para ver los participantes"
        )
    
    # Get virtual session
    virtual_session = db.query(VirtualSession).filter(VirtualSession.id == session_id).first()
    if not virtual_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sesión virtual no encontrada"
        )
    
    # Get participants (attendances with this session code)
    participants = db.query(Attendance, User).join(
        User, Attendance.user_id == User.id
    ).filter(
        Attendance.session_code == virtual_session.session_code
    ).all()
    
    participants_data = []
    for attendance, user in participants:
        participants_data.append({
            "user_id": user.id,
            "user_name": f"{user.first_name} {user.last_name}",
            "user_email": user.email,
            "check_in_time": attendance.check_in_time,
            "check_out_time": attendance.check_out_time,
            "duration_minutes": attendance.duration_minutes,
            "connection_quality": attendance.connection_quality,
            "device_info": attendance.device_info,
            "browser_info": attendance.browser_info,
            "status": attendance.status,
            "completion_percentage": attendance.completion_percentage,
            "is_online": attendance.check_in_time is not None and attendance.check_out_time is None
        })
    
    return {
        "virtual_session": {
            "id": virtual_session.id,
            "course_name": virtual_session.course_name,
            "session_date": virtual_session.session_date,
            "session_code": virtual_session.session_code,
            "max_participants": virtual_session.max_participants
        },
        "participants": participants_data,
        "total_participants": len(participants_data),
        "online_participants": len([p for p in participants_data if p["is_online"]])
    }


@router.put("/virtual-sessions/{session_id}", response_model=dict)
async def update_virtual_session(
    session_id: int,
    session_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update a virtual session (Admin only)
    """
    # Check if user is admin
    if current_user.role not in ["admin", "trainer", "supervisor"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para actualizar sesiones virtuales"
        )
    
    # Get virtual session
    virtual_session = db.query(VirtualSession).filter(VirtualSession.id == session_id).first()
    if not virtual_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sesión virtual no encontrada"
        )
    
    # Helper to normalize any incoming datetime to UTC naive for consistent storage
    def _to_utc_naive(dt: datetime | None) -> datetime | None:
        if dt is None:
            return None
        if getattr(dt, "tzinfo", None) is not None:
            try:
                return dt.astimezone(timezone.utc).replace(tzinfo=None)
            except Exception:
                pass
        return dt

    # Parse session_date if it's a string and normalize to UTC naive
    session_date = session_data.get("session_date")
    if isinstance(session_date, str):
        session_date = datetime.fromisoformat(session_date.replace('Z', '+00:00'))
    session_date = _to_utc_naive(session_date)
    
    # Parse end_date if it's a string and normalize to UTC naive
    end_date = session_data.get("end_date")
    if isinstance(end_date, str):
        end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    end_date = _to_utc_naive(end_date)
    
    # Validate dates if both are provided
    if session_date and end_date and end_date <= session_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La fecha de finalización debe ser posterior a la fecha de inicio"
        )
    elif session_date and not end_date:
        # If only session_date is updated, keep existing end_date or calculate new one
        if virtual_session.end_date:
            # Maintain the same duration
            current_duration = virtual_session.end_date - virtual_session.session_date
            end_date = session_date + current_duration
        else:
            # Default to 2 hours after session_date
            end_date = session_date + timedelta(hours=2)
    elif end_date and not session_date:
        # If only end_date is updated, validate against existing session_date
        if end_date <= virtual_session.session_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La fecha de finalización debe ser posterior a la fecha de inicio"
            )
    
    # Calculate valid_until based on end_date
    valid_until = end_date if end_date else virtual_session.valid_until
    
    # Update virtual session fields
    if session_data.get("course_name") is not None:
        virtual_session.course_name = session_data.get("course_name")
    if session_date is not None:
        virtual_session.session_date = session_date
    if end_date is not None:
        virtual_session.end_date = end_date
        virtual_session.valid_until = valid_until
    if session_data.get("virtual_session_link") is not None:
        virtual_session.virtual_session_link = session_data.get("virtual_session_link")
    if session_data.get("max_participants") is not None:
        virtual_session.max_participants = session_data.get("max_participants")
    if session_data.get("description") is not None:
        virtual_session.description = session_data.get("description")
    
    virtual_session.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(virtual_session)
    
    return {
        "success": True,
        "message": "Sesión virtual actualizada exitosamente",
        "virtual_session": {
            "id": virtual_session.id,
            "course_name": virtual_session.course_name,
            "session_date": virtual_session.session_date,
            "end_date": virtual_session.end_date,
            "virtual_session_link": virtual_session.virtual_session_link,
            "session_code": virtual_session.session_code,
            "valid_until": virtual_session.valid_until,
            "max_participants": virtual_session.max_participants,
            "description": virtual_session.description,
            "is_active": virtual_session.is_active,
            "updated_at": virtual_session.updated_at,
            "duration_minutes": virtual_session.duration_minutes
        }
    }


@router.delete("/virtual-sessions/{session_id}", response_model=dict)
async def delete_virtual_session(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Delete a virtual session (Admin only)
    """
    # Check if user is admin
    if current_user.role not in ["admin", "trainer", "supervisor"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para eliminar sesiones virtuales"
        )
    
    # Get virtual session
    virtual_session = db.query(VirtualSession).filter(VirtualSession.id == session_id).first()
    if not virtual_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sesión virtual no encontrada"
        )
    
    # Check if there are any attendance records associated with this session
    attendance_count = db.query(Attendance).filter(
        Attendance.session_code == virtual_session.session_code
    ).count()
    
    if attendance_count > 0:
        # Instead of deleting, mark as inactive to preserve attendance records
        virtual_session.is_active = False
        virtual_session.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "success": True,
            "message": f"Sesión virtual desactivada exitosamente. Se preservaron {attendance_count} registros de asistencia.",
            "attendance_records_preserved": attendance_count
        }
    else:
        # No attendance records, safe to delete
        db.delete(virtual_session)
        db.commit()
        
        return {
            "success": True,
            "message": "Sesión virtual eliminada exitosamente",
            "attendance_records_preserved": 0
        }


@router.get("/{attendance_id}", response_model=AttendanceResponse)
async def get_attendance_record(
    attendance_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get attendance record by ID
    """
    attendance = db.query(Attendance).filter(Attendance.id == attendance_id).first()

    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registro de asistencia no encontrado",
        )

    # Users can only see their own attendance unless they are admin or capacitador
    if (
        current_user.role.value not in ["admin", "trainer"]
        and attendance.user_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    return attendance


@router.put("/{attendance_id}", response_model=AttendanceResponse)
async def update_attendance_record(
    attendance_id: int,
    attendance_data: AttendanceUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Update attendance record
    """
    attendance = db.query(Attendance).filter(Attendance.id == attendance_id).first()

    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attendance record not found"
        )

    # Users can only update their own attendance unless they are admin or capacitador
    if (
        current_user.role.value not in ["admin", "trainer"]
        and attendance.user_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    # Update attendance fields
    update_data = attendance_data.dict(exclude_unset=True)

    # Apply updates first
    for field, value in update_data.items():
        setattr(attendance, field, value)

    # Calculate duration automatically if both check_in_time and check_out_time are present
    if attendance.check_in_time and attendance.check_out_time:
        check_in = attendance.check_in_time
        check_out = attendance.check_out_time

        # Calculate duration in minutes
        duration = check_out - check_in
        attendance.duration_minutes = int(duration.total_seconds() / 60)

        # Set scheduled_duration_minutes to the same value if not already set
        if not attendance.scheduled_duration_minutes:
            attendance.scheduled_duration_minutes = attendance.duration_minutes

        # Calculate completion percentage
        if (
            attendance.scheduled_duration_minutes
            and attendance.scheduled_duration_minutes > 0
        ):
            attendance.completion_percentage = min(
                100.0,
                (attendance.duration_minutes / attendance.scheduled_duration_minutes)
                * 100,
            )

    db.commit()
    db.refresh(attendance)

    return attendance


@router.delete("/{attendance_id}", response_model=MessageResponse)
async def delete_attendance_record(
    attendance_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Delete attendance record (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "trainer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    attendance = db.query(Attendance).filter(Attendance.id == attendance_id).first()

    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attendance record not found"
        )

    db.delete(attendance)
    db.commit()

    return MessageResponse(message="Registro de asistencia eliminado exitosamente")


@router.post("/check-in", response_model=AttendanceResponse)
async def check_in(
    course_id: int,
    location: str = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Check in to a course session
    """
    # Check if course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )

    # Check if user already checked in today
    today = datetime.now().date()
    existing_attendance = (
        db.query(Attendance)
        .filter(
            and_(
                Attendance.user_id == current_user.id,
                Attendance.course_id == course_id,
                func.date(Attendance.session_date) == today,
            )
        )
        .first()
    )

    if existing_attendance:
        if existing_attendance.check_in_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Already checked in for today",
            )
        # Update existing record
        existing_attendance.check_in_time = datetime.now()
        existing_attendance.status = AttendanceStatus.PRESENT
        existing_attendance.location = location
        db.commit()
        db.refresh(existing_attendance)
        return existing_attendance

    # Create new attendance record
    attendance = Attendance(
        user_id=current_user.id,
        course_id=course_id,
        session_date=datetime.now(),
        check_in_time=datetime.now(),
        status=AttendanceStatus.PRESENT,
        attendance_type=AttendanceType.IN_PERSON,
        location=location,
    )

    db.add(attendance)
    db.commit()
    db.refresh(attendance)

    return attendance


@router.post("/check-out/{attendance_id}", response_model=AttendanceResponse)
async def check_out(
    attendance_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Check out from a course session
    """
    attendance = db.query(Attendance).filter(Attendance.id == attendance_id).first()

    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attendance record not found"
        )

    # Users can only check out their own attendance
    if attendance.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    if not attendance.check_in_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must check in before checking out",
        )

    if attendance.check_out_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Already checked out"
        )

    # Update check out time and calculate duration
    attendance.check_out_time = datetime.now()
    duration = attendance.check_out_time - attendance.check_in_time
    attendance.duration_minutes = int(duration.total_seconds() / 60)

    # Calculate completion percentage if scheduled duration is set
    if attendance.scheduled_duration_minutes:
        attendance.completion_percentage = min(
            (attendance.duration_minutes / attendance.scheduled_duration_minutes) * 100,
            100.0,
        )

    db.commit()
    db.refresh(attendance)

    return attendance


@router.get("/summary/user/{user_id}", response_model=AttendanceSummary)
async def get_user_attendance_summary(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get attendance summary for a user
    """
    if (
        current_user.role.value not in ["admin", "trainer"]
        and current_user.id != user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    query = db.query(Attendance).filter(Attendance.user_id == user_id)

    total_sessions = query.count()
    present_sessions = query.filter(
        Attendance.status == AttendanceStatus.PRESENT
    ).count()
    absent_sessions = query.filter(Attendance.status == AttendanceStatus.ABSENT).count()
    late_sessions = query.filter(Attendance.status == AttendanceStatus.LATE).count()

    attendance_rate = (
        (present_sessions / total_sessions * 100) if total_sessions > 0 else 0
    )

    return AttendanceSummary(
        user_id=user_id,
        total_sessions=total_sessions,
        present_sessions=present_sessions,
        absent_sessions=absent_sessions,
        late_sessions=late_sessions,
        attendance_rate=attendance_rate,
    )

@router.delete("/sessions/{session_id}", response_model=MessageResponse)
async def delete_session(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Delete session (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "trainer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    db.delete(session)
    db.commit()

    return MessageResponse(message="Session deleted successfully")


@router.post("/bulk-register", response_model=BulkAttendanceResponse)
async def bulk_register_attendance(
    bulk_data: BulkAttendanceCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Register attendance for multiple users in a session with email notifications
    (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "trainer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    # Check if session exists
    session = (
        db.query(SessionModel).filter(SessionModel.id == bulk_data.session_id).first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    # Get course information
    course = db.query(Course).filter(Course.id == session.course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )

    successful_registrations = 0
    failed_registrations = 0
    notifications_sent = 0
    errors = []

    for user_id in bulk_data.user_ids:
        try:
            # Check if user exists
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                errors.append(f"User with ID {user_id} not found")
                failed_registrations += 1
                continue

            # Check if user is enrolled in the course
            enrollment = (
                db.query(Enrollment)
                .filter(
                    and_(
                        Enrollment.user_id == user_id, Enrollment.course_id == course.id
                    )
                )
                .first()
            )
            if not enrollment:
                errors.append(
                    f"User {user.username} is not enrolled in course {course.title}"
                )
                failed_registrations += 1
                continue

            # Check if attendance record already exists
            existing_attendance = (
                db.query(Attendance)
                .filter(
                    and_(
                        Attendance.user_id == user_id,
                        Attendance.session_id == bulk_data.session_id,
                    )
                )
                .first()
            )

            if existing_attendance:
                # Update existing record
                existing_attendance.status = bulk_data.status
                existing_attendance.attendance_type = bulk_data.attendance_type
                existing_attendance.location = bulk_data.location
                existing_attendance.notes = bulk_data.notes
                existing_attendance.verified_by = current_user.id
                existing_attendance.verified_at = datetime.now()
                existing_attendance.updated_at = datetime.now()
            else:
                # Create new attendance record
                attendance = Attendance(
                    user_id=user_id,
                    course_name=course.title,  # Store course name for compatibility
                    enrollment_id=enrollment.id,  # Link to enrollment for direct course_id access
                    session_id=bulk_data.session_id,
                    session_date=datetime.combine(
                        session.session_date, session.start_time
                    ),
                    status=bulk_data.status,
                    attendance_type=bulk_data.attendance_type,
                    check_in_time=(
                        datetime.now()
                        if bulk_data.status == AttendanceStatus.PRESENT
                        else None
                    ),
                    location=bulk_data.location,
                    notes=bulk_data.notes,
                    verified_by=current_user.id,
                    verified_at=datetime.now(),
                )
                db.add(attendance)

            successful_registrations += 1

            # Send email notification if requested
            if bulk_data.send_notifications and user.email:
                try:
                    # Create notification data
                    notification_data = AttendanceNotificationData(
                        user_name=user.full_name or user.username,
                        user_email=user.email,
                        course_title=course.title,
                        session_title=session.title,
                        session_date=session.session_date.strftime("%d/%m/%Y"),
                        session_time=f"{session.start_time.strftime('%H:%M')} - {session.end_time.strftime('%H:%M')}",
                        location=bulk_data.location or session.location,
                        status=bulk_data.status.value,
                    )

                    # Create notification message
                    status_text = {
                        "present": "presente",
                        "absent": "ausente",
                        "late": "tardanza",
                        "excused": "justificado",
                        "partial": "parcial",
                    }.get(bulk_data.status.value, bulk_data.status.value)

                    message = f"""
                    Estimado/a {notification_data.user_name},
                    
                    Se ha registrado su asistencia para la capacitación:
                    
                    Curso: {notification_data.course_title}
                    Sesión: {notification_data.session_title}
                    Fecha: {notification_data.session_date}
                    Horario: {notification_data.session_time}
                    Ubicación: {notification_data.location or 'No especificada'}
                    Estado: {status_text.upper()}
                    
                    Gracias por su participación.
                    
                    Saludos cordiales,
                    Sistema de Capacitación
                    """

                    # Create notification record
                    notification = Notification(
                        user_id=user_id,
                        title=f"Registro de Asistencia - {course.title}",
                        message=message,
                        notification_type=NotificationType.EMAIL,
                        priority=NotificationPriority.NORMAL,
                        created_by=current_user.id,
                    )
                    db.add(notification)
                    notifications_sent += 1

                except Exception as e:
                    errors.append(
                        f"Error al enviar notificación a {user.email}: {str(e)}"
                    )

        except Exception as e:
            errors.append(f"Error al procesar usuario {user_id}: {str(e)}")
            failed_registrations += 1

    # Commit all changes
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al guardar registros de asistencia: {str(e)}",
        )

    return BulkAttendanceResponse(
        session_id=bulk_data.session_id,
        total_users=len(bulk_data.user_ids),
        successful_registrations=successful_registrations,
        failed_registrations=failed_registrations,
        notifications_sent=notifications_sent,
        errors=errors,
    )


@router.get("/sessions/{session_id}/attendance-list")
async def generate_attendance_list_pdf(
    session_id: int,
    download: bool = Query(
        False, description="Set to true to download the file with a custom filename"
    ),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Generate attendance list PDF for a session (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "trainer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    # Check if session exists
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    # Get course information
    course = db.query(Course).filter(Course.id == session.course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )

    # Get enrolled users for this course
    enrolled_users_query = (
        db.query(User).join(Enrollment).filter(Enrollment.course_id == course.id)
    )

    # Filter out users who are marked as absent for this specific session
    # Get attendance records for this session
    absent_user_ids = (
        db.query(Attendance.user_id)
        .filter(
            and_(
                Attendance.session_id == session_id,
                Attendance.status == AttendanceStatus.ABSENT,
            )
        )
        .subquery()
    )

    # Exclude absent users from the list
    enrolled_users = (
        enrolled_users_query.filter(~User.id.in_(absent_user_ids))
        .order_by(User.first_name, User.last_name)
        .all()
    )

    if not enrolled_users:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontraron usuarios inscritos para este curso o todos los usuarios están marcados como ausentes",
        )

    # Create PDF using HTML template
    try:
        # Construir datos de sesión para la plantilla
        session_data = {
            "title": session.title,
            "session_date": session.session_date.strftime("%d/%m/%Y"),
            "course_title": course.title,
            "location": session.location or "",
            "duration": f"{getattr(session, 'duration_minutes', 0) or 0} min",
            "attendance_percentage": 100,  # Puedes calcularlo si tienes datos
        }

        # Construir lista de asistentes para la plantilla
        attendees = []
        for user in enrolled_users:
            # Buscar el Worker asociado al User para obtener el cargo
            worker = db.query(Worker).filter(Worker.user_id == user.id).first()
            position = ""
            area = ""
            if worker:
                position = worker.position or ""
                # Obtener el área del worker si tiene relación con area_obj
                if worker.area_obj:
                    area = worker.area_obj.name or ""
                else:
                    area = worker.department or ""
            else:
                # Fallback al User si no hay Worker
                position = getattr(user, "position", "") or ""
                area = getattr(user, "department", "") or ""

            attendees.append(
                {
                    "name": f"{user.first_name} {user.last_name}",
                    "document": getattr(user, "document_number", ""),
                    "position": position,
                    "area": area,
                }
            )

        # Preparar datos para el servicio de PDF
        template_data = {"session": session_data, "attendees": attendees}

        pdf_service = HTMLToPDFConverter()
        # Guardar PDF en archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            pdf_path = tmp_file.name
            pdf_bytes = pdf_service.generate_attendance_list_pdf(
                template_data, output_path=pdf_path
            )

        # Validar PDF generado (debe existir y ser un PDF válido)
        is_valid_pdf = False
        if os.path.exists(pdf_path):
            try:
                with open(pdf_path, "rb") as f:
                    header = f.read(4)
                    is_valid_pdf = header == b"%PDF"
            except Exception:
                is_valid_pdf = False

        if not is_valid_pdf:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
            return Response(
                content="Error generando PDF válido",
                media_type="text/plain",
                status_code=500,
            )

        # Nombre de archivo para descarga
        filename = f"lista_asistencia_{session_id}.pdf"
        # Si se solicita descarga, agregar header
        response_params = {
            "path": pdf_path,
            "media_type": "application/pdf",
            "background": BackgroundTask(lambda: os.remove(pdf_path)),
        }
        if download:
            response_params["filename"] = filename
        return FileResponse(**response_params)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al generar PDF de lista de asistencia: {str(e)}",
        )


@router.get("/{attendance_id}/certificate", response_class=FileResponse)
async def generate_attendance_certificate(
    attendance_id: int,
    download: bool = Query(False, description="Si true, fuerza la descarga del archivo"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Generar certificado de asistencia individual en PDF horizontal
    """
    try:
        # Obtener el registro de asistencia
        attendance = db.query(Attendance).filter(Attendance.id == attendance_id).first()

        if not attendance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registro de asistencia no encontrado"
            )

        # Verificar permisos: admin, trainer, supervisor o el propio usuario
        user_role = getattr(current_user, 'role', None) or getattr(current_user, 'rol', None)
        if (user_role not in ['admin', 'trainer', 'supervisor'] and 
            current_user.id != attendance.user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para generar este certificado"
            )

        # Obtener información del usuario
        user = db.query(User).filter(User.id == attendance.user_id).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )

        # Obtener información del curso por nombre si existe
        course = None
        course_title = attendance.course_name or "Curso"
        if attendance.course_name:
            course = db.query(Course).filter(Course.title == attendance.course_name).first()
            if course:
                course_title = course.title

        # Preparar datos de asistencia
        attendance_data = {
            'course_name': course_title,
            'session_date': attendance.session_date,  # Pasar objeto datetime
            'location': course.location if course else 'No especificado',
            'duration_minutes': attendance.duration_minutes or 0,
            'status': attendance.status.value if hasattr(attendance.status, 'value') else attendance.status,
            'completion_percentage': attendance.completion_percentage or 100,
            'notes': attendance.notes or ''
        }

        # Preparar datos del participante
        participant_data = {
            'first_name': user.first_name,
            'last_name': user.last_name,
            'full_name': user.full_name,  # Agregar nombre completo para mostrar todos los nombres y apellidos
            'document': user.document_number or '',
            'phone': user.phone or '',
            'position': user.position or '',
            'area': user.department or ''  # Usar department como área
        }

        # Generar PDF usando el servicio
        pdf_service = HTMLToPDFConverter()
        
        # Guardar PDF en archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            pdf_path = tmp_file.name
            pdf_bytes = pdf_service.generate_attendance_certificate_pdf(
                attendance_data, participant_data, output_path=pdf_path
            )

        # Validar PDF generado
        is_valid_pdf = False
        if os.path.exists(pdf_path):
            try:
                with open(pdf_path, "rb") as f:
                    header = f.read(4)
                    is_valid_pdf = header == b"%PDF"
            except Exception:
                is_valid_pdf = False

        if not is_valid_pdf:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error generando PDF válido"
            )

        # Nombre de archivo para descarga
        safe_user_name = "".join(c for c in f"{user.first_name}_{user.last_name}" if c.isalnum() or c in "._-")
        safe_course_name = "".join(c for c in course_title if c.isalnum() or c in "._-")[:20]
        filename = f"certificado_asistencia_{safe_user_name}_{safe_course_name}.pdf"
        
        # Configurar respuesta
        response_params = {
            "path": pdf_path,
            "media_type": "application/pdf",
            "background": BackgroundTask(lambda: os.remove(pdf_path)),
        }
        
        if download:
            response_params["filename"] = filename
            
        response = FileResponse(**response_params)
        
        # Agregar headers adicionales para asegurar la descarga
        if download:
            response.headers["Content-Disposition"] = f"attachment; filename={filename}"
            response.headers["Content-Type"] = "application/pdf"
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            
        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al generar certificado de asistencia: {str(e)}",
        )


@router.get("/sessions/{session_id}/participants-list")
async def generate_participants_list_pdf(
    session_id: int,
    download: bool = Query(
        False, description="Set to true to download the file with a custom filename"
    ),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Generate participants list PDF for a session with all enrolled users (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "trainer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    # Check if session exists
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    # Get course information
    course = db.query(Course).filter(Course.id == session.course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )

    # Get all enrolled users for this course (including those marked as absent)
    enrolled_users = (
        db.query(User)
        .join(Enrollment)
        .filter(Enrollment.course_id == course.id)
        .order_by(User.first_name, User.last_name)
        .all()
    )

    if not enrolled_users:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontraron usuarios inscritos para este curso",
        )

    # Create PDF using HTML template
    try:
        # Construir datos de sesión para la plantilla
        session_data = {
            "title": session.title,
            "session_date": session.session_date.strftime("%d/%m/%Y"),
            "course_title": course.title,
            "location": session.location or "",
            "duration": f"{getattr(session, 'duration_minutes', 0) or 0} min",
            "attendance_percentage": 100,  # Puedes calcularlo si tienes datos
        }

        # Construir lista completa de participantes para la plantilla
        attendees = []
        for user in enrolled_users:
            attendees.append(
                {
                    "name": f"{user.first_name} {user.last_name}",
                    "document": getattr(user, "document_number", ""),
                    "position": getattr(user, "position", ""),
                    "area": getattr(user, "area", ""),
                }
            )

        # Preparar datos para el servicio de PDF
        template_data = {"session": session_data, "attendees": attendees}

        pdf_service = HTMLToPDFConverter()
        # Guardar PDF en archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            pdf_path = tmp_file.name
            pdf_bytes = pdf_service.generate_attendance_list_pdf(
                template_data, output_path=pdf_path
            )

        # Validar PDF generado (debe existir y ser un PDF válido)
        is_valid_pdf = False
        if os.path.exists(pdf_path):
            try:
                with open(pdf_path, "rb") as f:
                    header = f.read(4)
                    is_valid_pdf = header == b"%PDF"
            except Exception:
                is_valid_pdf = False

        if not is_valid_pdf:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
            return Response(
                content="Error generando PDF válido",
                media_type="text/plain",
                status_code=500,
            )

        # Nombre de archivo para descarga
        filename = f"lista_participantes_{session_id}.pdf"
        # Si se solicita descarga, agregar header
        response_params = {
            "path": pdf_path,
            "media_type": "application/pdf",
            "background": BackgroundTask(lambda: os.remove(pdf_path)),
        }
        if download:
            response_params["filename"] = filename
        return FileResponse(**response_params)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al generar PDF de lista de participantes: {str(e)}",
        )


@router.post("/{attendance_id}/send-certificate", response_model=CertificateResponse)
async def send_attendance_certificate(
    attendance_id: int,
    request: CertificateRequest = CertificateRequest(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Enviar (emitir) un certificado al empleado desde el registro de asistencia.
    - Solo permitido para rol admin.
    - Crea el registro de Certificate y genera el PDF asociado.
    - El certificado quedará disponible en "Mis certificados" del empleado.
    """

    # Validar rol del usuario
    user_role = getattr(current_user, "role", None) or getattr(current_user, "rol", None)
    role_value = user_role.value if hasattr(user_role, "value") else user_role
    if role_value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para enviar certificados",
        )

    # Obtener asistencia
    attendance = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registro de asistencia no encontrado",
        )

    # Validar que el usuario exista
    user = db.query(User).filter(User.id == attendance.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    # Determinar el curso asociado (opcional)
    course_id = None
    course = None
    
    # Si se proporciona course_id como parámetro, usarlo directamente
    if request.course_id:
        # Verificar que el curso existe
        course_exists = db.query(Course).filter(Course.id == request.course_id).first()
        if not course_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El curso con ID {request.course_id} no existe",
            )
        course_id = request.course_id
        course = course_exists

    # Evitar duplicados: mismo usuario/fecha/asistencia usando plantilla 'attendance'
    # Para certificados de asistencia, verificamos por usuario, fecha y tipo de plantilla
    existing_query = db.query(Certificate).filter(
        Certificate.user_id == user.id,
        Certificate.completion_date == attendance.session_date,
        Certificate.template_used == "attendance",
    )
    
    # Si hay course_id, también verificar por curso para evitar duplicados específicos
    if course_id:
        existing_query = existing_query.filter(Certificate.course_id == course_id)
    else:
        # Si no hay course_id, verificar que no exista otro certificado sin curso para la misma fecha
        existing_query = existing_query.filter(Certificate.course_id.is_(None))
    
    existing = existing_query.first()
    if existing:
        # Si existe, regenerar el PDF si falta la ruta
        if not existing.file_path:
            generator = CertificateGenerator(db)
            try:
                await generator.generate_certificate_pdf(existing.id)
            except Exception:
                pass
        return existing

    # Crear certificado
    cert_number = uuid.uuid4().hex[:12].upper()
    verification_code = uuid.uuid4().hex[:8].upper()
    certificate = Certificate(
        user_id=user.id,
        course_id=course_id,
        certificate_number=cert_number,
        title=f"Certificado de Asistencia{f' - {course.title}' if course else f' - {attendance.course_name}' if attendance.course_name else ''}",
        description="Certificado de asistencia generado desde el módulo de asistencias",
        completion_date=attendance.session_date,
        issue_date=datetime.utcnow(),
        status=CertificateStatus.ISSUED,
        template_used="attendance",
        issued_by=current_user.id,
        verification_code=verification_code,
    )
    db.add(certificate)
    db.commit()
    db.refresh(certificate)

    # Generar PDF y actualizar ruta
    generator = CertificateGenerator(db)
    try:
        await generator.generate_certificate_pdf(certificate.id)
    except Exception as e:
        # Mantener el certificado aunque falle la generación de PDF
        print(f"Error generando PDF del certificado {certificate.id}: {str(e)}")

    return certificate


# ==================== VIRTUAL ATTENDANCE ENDPOINTS ====================

def generate_session_code(length: int = 8) -> str:
    """Generate a random session code for virtual attendance"""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


@router.post("/virtual/generate-code", response_model=dict)
async def generate_virtual_session_code(
    request: SessionCodeGenerate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Generate a session code for virtual attendance
    Only facilitators/admins can generate codes
    """
    # Check if user has permission to generate codes
    if current_user.role not in ["admin", "trainer", "supervisor"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para generar códigos de sesión"
        )
    
    # Generate unique session code
    session_code = generate_session_code()
    
    # Store the session code with expiration (you might want to create a separate table for this)
    # For now, we'll return the code and let the frontend handle validation timing
    
    return {
        "session_code": session_code,
        "course_name": request.course_name,
        "session_date": request.session_date,
        "valid_until": datetime.utcnow() + timedelta(minutes=request.valid_duration_minutes),
        "generated_by": current_user.id,
        "message": f"Código de sesión generado: {session_code}"
    }


@router.post("/virtual/check-in", response_model=VirtualAttendanceResponse)
async def virtual_attendance_check_in(
    request: VirtualAttendanceCheckIn,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Check-in for virtual attendance
    """
    # Verify user can check-in (either for themselves or if they're admin)
    if current_user.id != request.user_id and current_user.role not in ["admin", "trainer", "supervisor"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes registrar asistencia para otro usuario"
        )
    
    # Check if user already has attendance for this session
    existing_attendance = db.query(Attendance).filter(
        and_(
            Attendance.user_id == request.user_id,
            Attendance.course_name == request.course_name,
            func.date(Attendance.session_date) == func.date(request.session_date)
        )
    ).first()
    
    if existing_attendance:
        # If already checked in, update check-in time
        if existing_attendance.check_in_time:
            return VirtualAttendanceResponse(
                id=existing_attendance.id,
                status="already_checked_in",
                message="Ya tienes registro de entrada para esta sesión",
                check_in_time=existing_attendance.check_in_time,
                check_out_time=existing_attendance.check_out_time,
                duration_minutes=existing_attendance.duration_minutes,
                minimum_duration_met=existing_attendance.minimum_duration_met or False
            )
        else:
            # Update existing record with check-in
            existing_attendance.check_in_time = datetime.utcnow()
            existing_attendance.attendance_type = AttendanceType.VIRTUAL
            existing_attendance.status = AttendanceStatus.PRESENT
            existing_attendance.session_code = request.session_code
            existing_attendance.virtual_session_link = request.virtual_session_link
            existing_attendance.device_fingerprint = request.device_fingerprint
            existing_attendance.browser_info = request.browser_info
            existing_attendance.ip_address = request.ip_address
            existing_attendance.session_code_used_at = datetime.utcnow()
            
            db.commit()
            db.refresh(existing_attendance)
            
            return VirtualAttendanceResponse(
                id=existing_attendance.id,
                status="checked_in",
                message="Entrada registrada exitosamente",
                check_in_time=existing_attendance.check_in_time,
                session_code=request.session_code
            )
    
    # Create new attendance record
    new_attendance = Attendance(
        user_id=request.user_id,
        course_name=request.course_name,
        session_date=request.session_date,
        status=AttendanceStatus.PRESENT,
        attendance_type=AttendanceType.VIRTUAL,
        check_in_time=datetime.utcnow(),
        session_code=request.session_code,
        virtual_session_link=request.virtual_session_link,
        device_fingerprint=request.device_fingerprint,
        browser_info=request.browser_info,
        ip_address=request.ip_address,
        session_code_used_at=datetime.utcnow(),
        completion_percentage=0.0
    )
    
    db.add(new_attendance)
    db.commit()
    db.refresh(new_attendance)
    
    return VirtualAttendanceResponse(
        id=new_attendance.id,
        status="checked_in",
        message="Entrada registrada exitosamente",
        check_in_time=new_attendance.check_in_time,
        session_code=request.session_code
    )


@router.post("/virtual/check-out", response_model=VirtualAttendanceResponse)
async def virtual_attendance_check_out(
    request: VirtualAttendanceCheckOut,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Check-out for virtual attendance
    """
    # Get attendance record
    attendance = db.query(Attendance).filter(Attendance.id == request.attendance_id).first()
    
    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registro de asistencia no encontrado"
        )
    
    # Verify user can check-out (either for themselves or if they're admin)
    if current_user.id != attendance.user_id and current_user.role not in ["admin", "trainer", "supervisor"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes modificar la asistencia de otro usuario"
        )
    
    # Check if already checked out
    if attendance.check_out_time:
        return VirtualAttendanceResponse(
            id=attendance.id,
            status="already_checked_out",
            message="Ya tienes registro de salida para esta sesión",
            check_in_time=attendance.check_in_time,
            check_out_time=attendance.check_out_time,
            duration_minutes=attendance.duration_minutes,
            minimum_duration_met=attendance.minimum_duration_met or False
        )
    
    # Update attendance with check-out
    check_out_time = datetime.utcnow()
    attendance.check_out_time = check_out_time
    attendance.connection_quality = request.connection_quality
    attendance.virtual_evidence = request.virtual_evidence
    if request.notes:
        attendance.notes = request.notes
    
    # Calculate duration
    if attendance.check_in_time:
        duration = check_out_time - attendance.check_in_time
        attendance.duration_minutes = int(duration.total_seconds() / 60)
        
        # Check if minimum duration was met (assume 80% of scheduled time or at least 30 minutes)
        minimum_required = max(30, int((attendance.scheduled_duration_minutes or 60) * 0.8))
        attendance.minimum_duration_met = attendance.duration_minutes >= minimum_required
        
        # Update completion percentage based on duration
        if attendance.scheduled_duration_minutes:
            attendance.completion_percentage = min(
                100.0, 
                (attendance.duration_minutes / attendance.scheduled_duration_minutes) * 100
            )
        else:
            attendance.completion_percentage = 100.0 if attendance.minimum_duration_met else 50.0
    
    db.commit()
    db.refresh(attendance)
    
    return VirtualAttendanceResponse(
        id=attendance.id,
        status="checked_out",
        message="Salida registrada exitosamente",
        check_in_time=attendance.check_in_time,
        check_out_time=attendance.check_out_time,
        duration_minutes=attendance.duration_minutes,
        minimum_duration_met=attendance.minimum_duration_met or False
    )


@router.post("/virtual/validate-code", response_model=dict)
async def validate_session_code(
    request: SessionCodeValidate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Validate a session code for virtual attendance
    """
    # Buscar la sesión por código y estado activo (sin filtrar por vencimiento en la consulta)
    virtual_session = db.query(VirtualSession).filter(
        and_(
            VirtualSession.session_code == request.session_code,
            VirtualSession.is_active == True,
        )
    ).first()

    if virtual_session is None:
        return {
            "valid": False,
            "message": "Código de sesión inválido",
        }

    # Verificar vencimiento utilizando tiempo actual en UTC
    now = datetime.utcnow()
    is_expired = now > virtual_session.valid_until

    # Conversión de fechas a hora de Colombia (America/Bogota)
    bogota_tz = ZoneInfo("America/Bogota")

    def to_bogota_iso(dt: Any) -> Optional[str]:
        if dt is None:
            return None
        # Si es datetime
        if isinstance(dt, datetime):
            # Convertir a aware UTC si es naive
            aware_utc = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
            return aware_utc.astimezone(bogota_tz).isoformat()
        # Si es date (sin tiempo), asumir 00:00 en UTC y convertir
        if isinstance(dt, date):
            base_dt = datetime.combine(dt, datetime.min.time())
            aware_utc = base_dt.replace(tzinfo=timezone.utc)
            return aware_utc.astimezone(bogota_tz).isoformat()
        # Fallback: representar como string
        try:
            return str(dt)
        except Exception:
            return None

    now_colombia = now.replace(tzinfo=timezone.utc).astimezone(bogota_tz).isoformat()

    if is_expired:
        return {
            "valid": False,
            "message": "Código de sesión expirado",
            "course_name": virtual_session.course_name,
            "session_date": virtual_session.session_date,
            "end_date": virtual_session.end_date,
            "valid_until": virtual_session.valid_until,
            "is_session_active": virtual_session.is_session_active,
            "is_session_expired": True,
            # Campos adicionales en hora local de Colombia
            "timezone": "America/Bogota",
            "now_utc": now.replace(tzinfo=timezone.utc).isoformat(),
            "now_colombia": now_colombia,
            "session_date_colombia": to_bogota_iso(virtual_session.session_date),
            "end_date_colombia": to_bogota_iso(virtual_session.end_date),
            "valid_until_colombia": to_bogota_iso(virtual_session.valid_until),
        }

    return {
        "valid": True,
        "message": "Código de sesión válido",
        "course_name": virtual_session.course_name,
        "session_date": virtual_session.session_date,
        "end_date": virtual_session.end_date,
        "virtual_session_link": virtual_session.virtual_session_link,
        "duration_minutes": virtual_session.duration_minutes,
        "is_session_active": virtual_session.is_session_active,
        "is_session_expired": False,
        # Campos adicionales en hora local de Colombia
        "timezone": "America/Bogota",
        "now_utc": now.replace(tzinfo=timezone.utc).isoformat(),
        "now_colombia": now_colombia,
        "session_date_colombia": to_bogota_iso(virtual_session.session_date),
        "end_date_colombia": to_bogota_iso(virtual_session.end_date),
        "valid_until_colombia": to_bogota_iso(virtual_session.valid_until),
    }


@router.get("/virtual/status/{user_id}", response_model=dict)
async def get_virtual_attendance_status(
    user_id: int,
    course_name: str = Query(..., description="Nombre del curso"),
    session_date: date = Query(..., description="Fecha de la sesión"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get virtual attendance status for a user and session
    """
    # Verify user can check status (either for themselves or if they're admin)
    if current_user.id != user_id and current_user.role not in ["admin", "trainer", "supervisor"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes consultar la asistencia de otro usuario"
        )
    
    # Get attendance record
    attendance = db.query(Attendance).filter(
        and_(
            Attendance.user_id == user_id,
            Attendance.course_name == course_name,
            func.date(Attendance.session_date) == session_date
        )
    ).first()
    
    if not attendance:
        return {
            "status": "not_registered",
            "message": "No hay registro de asistencia para esta sesión",
            "checked_in": False,
            "checked_out": False
        }
    
    return {
        "status": "registered",
        "attendance_id": attendance.id,
        "checked_in": attendance.check_in_time is not None,
        "checked_out": attendance.check_out_time is not None,
        "check_in_time": attendance.check_in_time,
        "check_out_time": attendance.check_out_time,
        "duration_minutes": attendance.duration_minutes,
        "minimum_duration_met": attendance.minimum_duration_met or False,
        "attendance_type": attendance.attendance_type,
        "completion_percentage": attendance.completion_percentage
    }
