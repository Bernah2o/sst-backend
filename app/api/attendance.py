from typing import Any
from datetime import datetime, date
import uuid
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
from app.models.attendance import Attendance, AttendanceStatus, AttendanceType
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

router = APIRouter()


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
    if current_user.role.value not in ["admin", "capacitador"]:
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
    if current_user.role.value not in ["admin", "capacitador"]:
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
    if current_user.role.value not in ["admin", "capacitador"]:
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
    if current_user.role.value not in ["admin", "capacitador"]:
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
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Get attendance records with optional filtering
    """
    query = db.query(Attendance)

    # Apply filters
    if user_id:
        # Users can only see their own attendance unless they are admin or capacitador
        if (
            current_user.role.value not in ["admin", "capacitador"]
            and current_user.id != user_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficientes"
            )
        query = query.filter(Attendance.user_id == user_id)
    elif current_user.role.value not in ["admin", "capacitador"]:
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
        current_user.role.value not in ["admin", "capacitador"]
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

    attendance = Attendance(**attendance_dict)
    db.add(attendance)
    db.commit()
    db.refresh(attendance)
    return attendance


@router.get("/stats")
async def get_attendance_stats(
    current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
) -> Any:
    """
    Get attendance statistics by status
    """
    # Check permissions
    if current_user.role.value not in ["admin", "capacitador"]:
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
    download: bool = Query(
        False, description="Set to true to download the file with a custom filename"
    ),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Generate attendance list PDF for all participants in a specific course session
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    try:
        # Parse session date
        session_date_obj = datetime.strptime(session_date, "%Y-%m-%d").date()
        
        # Get all attendance records for this course and date
        attendances = (
            db.query(Attendance)
            .join(User, Attendance.user_id == User.id)
            .filter(
                Attendance.course_name == course_name,
                func.date(Attendance.session_date) == session_date_obj
            )
            .order_by(User.first_name, User.last_name)
            .all()
        )

        if not attendances:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se encontraron registros de asistencia para este curso y fecha",
            )

        # Get course information (try to find from the first attendance record)
        first_attendance = attendances[0]
        course = db.query(Course).filter(Course.title == course_name).first()
        
        # Construir datos de sesión para la plantilla
        session_data = {
            "title": f"Lista de Asistencia - {course_name}",
            "session_date": session_date_obj.strftime("%d/%m/%Y"),
            "course_title": course_name,
            "instructor_name": course.instructor_name if course else "No asignado",
            "location": course.location if course else "No especificado",
            "duration": f"{first_attendance.duration_minutes or 0} min",
            "attendance_percentage": 100,
        }

        # Construir lista de participantes para la plantilla
        attendees = []
        for attendance in attendances:
            user = attendance.user
            attendees.append({
                "name": f"{user.first_name} {user.last_name}",
                "document": user.document_number or "",
                "position": user.position or "",
                "area": user.department or "",  # Usar department como área
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
        current_user.role.value not in ["admin", "capacitador"]
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
        current_user.role.value not in ["admin", "capacitador"]
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
    if current_user.role.value not in ["admin", "capacitador"]:
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
        current_user.role.value not in ["admin", "capacitador"]
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

    # Eliminado endpoint de resumen por curso porque ya no hay course_id en asistencia


@router.delete("/sessions/{session_id}", response_model=MessageResponse)
async def delete_session(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Delete session (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
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
    if current_user.role.value not in ["admin", "capacitador"]:
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
                    course_id=course.id,
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
    if current_user.role.value not in ["admin", "capacitador"]:
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
            "instructor_name": getattr(
                session,
                "instructor_name",
                f"{current_user.first_name} {current_user.last_name}",
            ),
            "location": session.location or "",
            "duration": f"{getattr(session, 'duration_minutes', 0) or 0} min",
            "attendance_percentage": 100,  # Puedes calcularlo si tienes datos
        }

        # Construir lista de asistentes para la plantilla
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
            'instructor_name': course.instructor_name if course else 'No asignado',
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
    if current_user.role.value not in ["admin", "capacitador"]:
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
            "instructor_name": getattr(
                session,
                "instructor_name",
                f"{current_user.first_name} {current_user.last_name}",
            ),
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

    # Determinar el curso asociado
    course_id = None
    if attendance.session_id:
        session = db.query(SessionModel).filter(SessionModel.id == attendance.session_id).first()
        if session:
            course_id = session.course_id
    if not course_id and attendance.enrollment_id:
        enrollment = db.query(Enrollment).filter(Enrollment.id == attendance.enrollment_id).first()
        if enrollment:
            course_id = enrollment.course_id
    if not course_id and attendance.course_name:
        # Intento exacto (case-insensitive)
        course_by_name = (
            db.query(Course)
            .filter(func.lower(Course.title) == func.lower(attendance.course_name))
            .first()
        )
        # Si no hay exacto, intento por coincidencia parcial
        if not course_by_name:
            course_by_name = (
                db.query(Course)
                .filter(Course.title.ilike(f"%{attendance.course_name}%"))
                .order_by(Course.created_at.desc())
                .first()
            )
        if course_by_name:
            course_id = course_by_name.id

    # Fallback: usar la inscripción más reciente del usuario si no se pudo resolver
    if not course_id:
        recent_enrollment = (
            db.query(Enrollment)
            .filter(Enrollment.user_id == user.id)
            .order_by(Enrollment.created_at.desc())
            .first()
        )
        if recent_enrollment:
            course_id = recent_enrollment.course_id

    if not course_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No se pudo determinar el curso del registro de asistencia"
            ),
        )

    course = db.query(Course).filter(Course.id == course_id).first()

    # Evitar duplicados: mismo usuario/curso/fecha usando plantilla 'attendance'
    existing = (
        db.query(Certificate)
        .filter(
            Certificate.user_id == user.id,
            Certificate.course_id == course_id,
            Certificate.completion_date == attendance.session_date,
            Certificate.template_used == "attendance",
        )
        .first()
    )
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
        title=f"Certificado de Asistencia - {course.title if course else 'Curso'}",
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
