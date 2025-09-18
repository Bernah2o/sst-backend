from typing import Any, List, Optional
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.dependencies import get_current_active_user
from app.database import get_db
from app.models.user import User, UserRole
from app.models.attendance import Attendance, AttendanceStatus, AttendanceType
from app.models.course import Course
from app.models.session import Session as SessionModel
from app.models.enrollment import Enrollment
from app.schemas.attendance import (
    AttendanceCreate,
    AttendanceUpdate,
    AttendanceResponse,
    AttendanceListResponse,
    BulkAttendanceCreate,
    BulkAttendanceResponse,
)
from app.schemas.common import MessageResponse, PaginatedResponse

router = APIRouter()


# Verificación de permisos de administrador
def check_admin_permissions(current_user: User):
    """Verificar que el usuario tenga permisos de administrador"""
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta funcionalidad es exclusiva para administradores",
        )


@router.get("/", response_model=PaginatedResponse[AttendanceListResponse])
async def get_all_attendance_records(
    skip: int = 0,
    limit: int = 100,
    user_id: Optional[int] = None,
    course_id: Optional[int] = None,
    session_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    status: Optional[AttendanceStatus] = None,
    attendance_type: Optional[AttendanceType] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Obtener todos los registros de asistencia con filtros avanzados (solo administradores)
    """
    # Verificar permisos de administrador
    check_admin_permissions(current_user)

    # Consulta base
    query = db.query(Attendance)

    # Aplicar filtros
    if user_id:
        query = query.filter(Attendance.user_id == user_id)

    # if course_id:
    #     query = query.filter(Attendance.course_id == course_id)  # Eliminado: ya no existe course_id

    if session_id:
        query = query.filter(Attendance.session_id == session_id)

    if start_date:
        query = query.filter(func.date(Attendance.session_date) >= start_date)

    if end_date:
        query = query.filter(func.date(Attendance.session_date) <= end_date)

    if status:
        query = query.filter(Attendance.status == status)

    if attendance_type:
        query = query.filter(Attendance.attendance_type == attendance_type)

    if search:
        # Buscar por nombre de usuario o curso
        user_ids = (
            db.query(User.id)
            .filter(
                or_(
                    User.first_name.ilike(f"%{search}%"),
                    User.last_name.ilike(f"%{search}%"),
                    User.email.ilike(f"%{search}%"),
                )
            )
            .all()
        )
        user_ids = [id[0] for id in user_ids]

        course_ids = db.query(Course.id).filter(Course.title.ilike(f"%{search}%")).all()
        course_ids = [id[0] for id in course_ids]

        query = query.filter(
            or_(
                Attendance.user_id.in_(user_ids),
                # Attendance.course_id.in_(course_ids),  # Eliminado: ya no existe course_id
                Attendance.notes.ilike(f"%{search}%"),
            )
        )

    # Obtener el total de registros
    total = query.count()

    # Aplicar paginación y ordenar por fecha de sesión (más reciente primero)
    attendance_records = (
        query.order_by(Attendance.session_date.desc()).offset(skip).limit(limit).all()
    )

    # Construir manualmente los datos de respuesta con información de usuario y curso
    attendance_data = []
    for record in attendance_records:
        # Obtener información del usuario
        user = db.query(User).filter(User.id == record.user_id).first()
        # Obtener información del curso
        course = db.query(Course).filter(Course.id == record.course_id).first()

        record_data = {
            "id": record.id,
            "user_id": record.user_id,
            "course_id": record.course_id,
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
            "user": (
                {
                    "id": user.id,
                    "name": f"{user.first_name} {user.last_name}",
                    "email": user.email,
                }
                if user
                else None
            ),
            "course": {"id": course.id, "title": course.title} if course else None,
        }
        attendance_data.append(record_data)

    # Calcular información de paginación
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
async def admin_create_attendance(
    attendance_data: AttendanceCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Crear un nuevo registro de asistencia (solo administradores)
    """
    # Verificar permisos de administrador
    check_admin_permissions(current_user)

    # Verificar que el usuario exista
    user = db.query(User).filter(User.id == attendance_data.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado"
        )

    # Verificar que el curso exista
    course = db.query(Course).filter(Course.id == attendance_data.course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Curso no encontrado"
        )

    # Verificar si ya existe un registro de asistencia para este usuario, curso y fecha
    existing_attendance = (
        db.query(Attendance)
        .filter(
            and_(
                Attendance.user_id == attendance_data.user_id,
                # Attendance.course_id == attendance_data.course_id,  # Eliminado: ya no existe course_id
                func.date(Attendance.session_date)
                == func.date(attendance_data.session_date),
            )
        )
        .first()
    )

    if existing_attendance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un registro de asistencia para este usuario, curso y fecha",
        )

    # Buscar la inscripción correspondiente
    enrollment = (
        db.query(Enrollment)
        .filter(
            and_(
                Enrollment.user_id == attendance_data.user_id,
                Enrollment.course_id == attendance_data.course_id,
            )
        )
        .first()
    )

    # Crear nuevo registro de asistencia
    attendance = Attendance(**attendance_data.dict())

    # Establecer campos adicionales
    attendance.enrollment_id = enrollment.id if enrollment else None
    attendance.verified_by = current_user.id
    attendance.verified_at = datetime.now()

    db.add(attendance)
    db.commit()
    db.refresh(attendance)

    return attendance


@router.put("/{attendance_id}", response_model=AttendanceResponse)
async def admin_update_attendance(
    attendance_id: int,
    attendance_data: AttendanceUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Actualizar un registro de asistencia (solo administradores)
    """
    # Verificar permisos de administrador
    check_admin_permissions(current_user)

    # Buscar el registro de asistencia
    attendance = db.query(Attendance).filter(Attendance.id == attendance_id).first()

    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registro de asistencia no encontrado",
        )

    # Actualizar campos
    update_data = attendance_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(attendance, field, value)

    # Actualizar campos de verificación
    attendance.verified_by = current_user.id
    attendance.verified_at = datetime.now()

    db.commit()
    db.refresh(attendance)

    return attendance


@router.delete("/{attendance_id}", response_model=MessageResponse)
async def admin_delete_attendance(
    attendance_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Eliminar un registro de asistencia (solo administradores)
    """
    # Verificar permisos de administrador
    check_admin_permissions(current_user)

    # Buscar el registro de asistencia
    attendance = db.query(Attendance).filter(Attendance.id == attendance_id).first()

    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registro de asistencia no encontrado",
        )

    # Eliminar el registro
    db.delete(attendance)
    db.commit()

    return MessageResponse(message="Registro de asistencia eliminado exitosamente")


@router.post("/bulk", response_model=BulkAttendanceResponse)
async def admin_bulk_create_attendance(
    bulk_data: BulkAttendanceCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Crear múltiples registros de asistencia a la vez (solo administradores)
    """
    # Verificar permisos de administrador
    check_admin_permissions(current_user)

    # Verificar que el curso exista
    course = db.query(Course).filter(Course.id == bulk_data.course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Curso no encontrado"
        )

    # Verificar que la sesión exista si se proporciona
    if bulk_data.session_id:
        session = (
            db.query(SessionModel)
            .filter(SessionModel.id == bulk_data.session_id)
            .first()
        )
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Sesión no encontrada"
            )

    # Resultados
    created_count = 0
    skipped_count = 0
    errors = []

    # Procesar cada usuario
    for user_id in bulk_data.user_ids:
        try:
            # Verificar que el usuario exista
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                errors.append(f"Usuario con ID {user_id} no encontrado")
                continue

            # Verificar si ya existe un registro para este usuario, curso y fecha
            existing_attendance = (
                db.query(Attendance)
                .filter(
                    and_(
                        Attendance.user_id == user_id,
                        # Attendance.course_id == bulk_data.course_id,  # Eliminado: ya no existe course_id
                        func.date(Attendance.session_date)
                        == func.date(bulk_data.session_date),
                    )
                )
                .first()
            )

            if existing_attendance:
                skipped_count += 1
                continue

            # Buscar la inscripción correspondiente
            enrollment = (
                db.query(Enrollment)
                .filter(
                    and_(
                        Enrollment.user_id == user_id,
                        Enrollment.course_id == bulk_data.course_id,
                    )
                )
                .first()
            )

            # Crear nuevo registro de asistencia
            attendance = Attendance(
                user_id=user_id,
                course_id=bulk_data.course_id,
                session_id=bulk_data.session_id,
                enrollment_id=enrollment.id if enrollment else None,
                session_date=bulk_data.session_date,
                status=bulk_data.status,
                attendance_type=bulk_data.attendance_type,
                location=bulk_data.location,
                notes=bulk_data.notes,
                verified_by=current_user.id,
                verified_at=datetime.now(),
            )

            db.add(attendance)
            created_count += 1

        except Exception as e:
            errors.append(f"Error al procesar usuario {user_id}: {str(e)}")

    # Confirmar cambios en la base de datos
    db.commit()

    return BulkAttendanceResponse(
        message=f"Proceso completado: {created_count} registros creados, {skipped_count} omitidos",
        created_count=created_count,
        skipped_count=skipped_count,
        errors=errors,
    )


@router.get("/stats/course/{course_id}", response_model=Any)
async def get_course_attendance_stats(
    course_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Obtener estadísticas de asistencia para un curso específico (solo administradores)
    """
    # Verificar permisos de administrador
    check_admin_permissions(current_user)

    # Verificar que el curso exista
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Curso no encontrado"
        )

    # Consulta base para estadísticas
    # query = db.query(Attendance).filter(Attendance.course_id == course_id)  # Eliminado: ya no existe course_id

    # Aplicar filtros de fecha si se proporcionan
    if start_date:
        query = query.filter(func.date(Attendance.session_date) >= start_date)

    if end_date:
        query = query.filter(func.date(Attendance.session_date) <= end_date)

    # Obtener todos los registros de asistencia para este curso
    attendance_records = query.all()

    # Calcular estadísticas
    total_records = len(attendance_records)
    present_count = sum(
        1 for record in attendance_records if record.status == AttendanceStatus.PRESENT
    )
    absent_count = sum(
        1 for record in attendance_records if record.status == AttendanceStatus.ABSENT
    )
    late_count = sum(
        1 for record in attendance_records if record.status == AttendanceStatus.LATE
    )
    excused_count = sum(
        1 for record in attendance_records if record.status == AttendanceStatus.EXCUSED
    )
    partial_count = sum(
        1 for record in attendance_records if record.status == AttendanceStatus.PARTIAL
    )

    # Calcular porcentajes
    attendance_rate = (present_count / total_records * 100) if total_records > 0 else 0
    absence_rate = (absent_count / total_records * 100) if total_records > 0 else 0

    # Obtener estadísticas por usuario
    user_stats = {}
    for record in attendance_records:
        if record.user_id not in user_stats:
            user = db.query(User).filter(User.id == record.user_id).first()
            user_stats[record.user_id] = {
                "user_id": record.user_id,
                "name": (
                    f"{user.first_name} {user.last_name}"
                    if user
                    else "Usuario desconocido"
                ),
                "email": user.email if user else "",
                "total_sessions": 0,
                "present": 0,
                "absent": 0,
                "late": 0,
                "excused": 0,
                "partial": 0,
                "attendance_rate": 0,
            }

        user_stats[record.user_id]["total_sessions"] += 1

        if record.status == AttendanceStatus.PRESENT:
            user_stats[record.user_id]["present"] += 1
        elif record.status == AttendanceStatus.ABSENT:
            user_stats[record.user_id]["absent"] += 1
        elif record.status == AttendanceStatus.LATE:
            user_stats[record.user_id]["late"] += 1
        elif record.status == AttendanceStatus.EXCUSED:
            user_stats[record.user_id]["excused"] += 1
        elif record.status == AttendanceStatus.PARTIAL:
            user_stats[record.user_id]["partial"] += 1

    # Calcular tasas de asistencia por usuario
    for user_id, stats in user_stats.items():
        stats["attendance_rate"] = (
            (
                (stats["present"] + stats["late"] + stats["partial"])
                / stats["total_sessions"]
                * 100
            )
            if stats["total_sessions"] > 0
            else 0
        )

    # Convertir diccionario a lista para la respuesta
    user_stats_list = list(user_stats.values())

    # Ordenar por tasa de asistencia (descendente)
    user_stats_list.sort(key=lambda x: x["attendance_rate"], reverse=True)

    return {
        "course": {
            "id": course.id,
            "title": course.title,
            "type": course.course_type.value if course.course_type else None,
        },
        "summary": {
            "total_records": total_records,
            "present_count": present_count,
            "absent_count": absent_count,
            "late_count": late_count,
            "excused_count": excused_count,
            "partial_count": partial_count,
            "attendance_rate": attendance_rate,
            "absence_rate": absence_rate,
        },
        "user_stats": user_stats_list,
    }
