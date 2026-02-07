"""
API endpoints for Committee Meetings Management
"""
import io
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc, asc, func
from datetime import datetime, date, timedelta

from app.database import get_db
from app.dependencies import get_current_user
from app.models.committee import (
    Committee, CommitteeMeeting, MeetingAttendance, CommitteeMember, CommitteeActivity
)
from app.models.user import User
from app.services.html_to_pdf import HTMLToPDFConverter

logger = logging.getLogger(__name__)
from app.schemas.committee import (
    CommitteeMeeting as CommitteeMeetingSchema,
    CommitteeMeetingCreate,
    CommitteeMeetingUpdate,
    MeetingAttendance as MeetingAttendanceSchema,
    MeetingAttendanceCreate,
    MeetingAttendanceUpdate,
    AttendanceStatusEnum
)

router = APIRouter()

# Committee Meeting endpoints
@router.get("/", response_model=List[CommitteeMeetingSchema])
@router.get("", response_model=List[CommitteeMeetingSchema])  # Add route without trailing slash to avoid 405 error
async def get_committee_meetings(
    committee_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener reuniones de comités con filtros"""
    query = db.query(CommitteeMeeting).options(
        joinedload(CommitteeMeeting.committee)
    )
    
    # Filtros
    if committee_id:
        query = query.filter(CommitteeMeeting.committee_id == committee_id)
    
    if status:
        query = query.filter(CommitteeMeeting.status == status)
    
    if date_from:
        query = query.filter(CommitteeMeeting.meeting_date >= date_from)
    
    if date_to:
        query = query.filter(CommitteeMeeting.meeting_date <= date_to)
    
    # Ordenar por fecha programada descendente
    query = query.order_by(desc(CommitteeMeeting.meeting_date))
    
    meetings = query.offset(skip).limit(limit).all()
    
    return meetings

@router.post("/", response_model=CommitteeMeetingSchema, status_code=status.HTTP_201_CREATED)
@router.post("", response_model=CommitteeMeetingSchema, status_code=status.HTTP_201_CREATED)  # Add route without trailing slash to avoid 307 redirect
async def create_committee_meeting(
    meeting: CommitteeMeetingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Crear una nueva reunión de comité"""
    # Verificar que el comité existe
    committee = db.query(Committee).filter(Committee.id == meeting.committee_id).first()
    if not committee:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Comité no encontrado"
        )
    
    # Verificar que la fecha no sea en el pasado
    if meeting.meeting_date.date() < date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La fecha de la reunión no puede ser en el pasado"
        )
    
    meeting_data = meeting.model_dump()
    meeting_data["created_by"] = current_user.id
    
    db_meeting = CommitteeMeeting(**meeting_data)
    db.add(db_meeting)
    db.commit()
    db.refresh(db_meeting)
    
    # Crear registros de asistencia para todos los miembros activos del comité
    active_members = db.query(CommitteeMember).filter(
        and_(
            CommitteeMember.committee_id == meeting.committee_id,
            CommitteeMember.is_active == True
        )
    ).all()
    
    for member in active_members:
        attendance = MeetingAttendance(
            meeting_id=db_meeting.id,
            member_id=member.id,
            attendance_status=AttendanceStatusEnum.ABSENT.value
        )
        db.add(attendance)
    
    db.commit()
    
    return db_meeting

@router.get("/{meeting_id}", response_model=CommitteeMeetingSchema)
async def get_committee_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener una reunión de comité por ID"""
    meeting = db.query(CommitteeMeeting).options(
        joinedload(CommitteeMeeting.committee)
    ).filter(CommitteeMeeting.id == meeting_id).first()
    
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reunión no encontrada"
        )
    
    return meeting

@router.put("/{meeting_id}", response_model=CommitteeMeetingSchema)
async def update_committee_meeting(
    meeting_id: int,
    meeting_update: CommitteeMeetingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Actualizar una reunión de comité"""
    meeting = db.query(CommitteeMeeting).filter(CommitteeMeeting.id == meeting_id).first()
    
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reunión no encontrada"
        )
    
    # Verificar que no se pueda modificar una reunión completada
    if meeting.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede modificar una reunión completada"
        )
    
    # Verificar fecha si se está actualizando
    if meeting_update.meeting_date and meeting_update.meeting_date.date() < date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La fecha de la reunión no puede ser en el pasado"
        )
    
    update_data = meeting_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(meeting, field, value)
    
    db.commit()
    db.refresh(meeting)
    
    return meeting

@router.get("/{meeting_id}/delete-preview")
async def get_meeting_delete_preview(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener información de lo que se eliminará al borrar una reunión"""
    meeting = db.query(CommitteeMeeting).filter(CommitteeMeeting.id == meeting_id).first()

    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reunión no encontrada"
        )

    attendance_count = db.query(MeetingAttendance).filter(
        MeetingAttendance.meeting_id == meeting_id
    ).count()

    activities_count = db.query(CommitteeActivity).filter(
        CommitteeActivity.meeting_id == meeting_id
    ).count()

    return {
        "meeting_id": meeting_id,
        "meeting_title": meeting.title,
        "attendance_count": attendance_count,
        "activities_count": activities_count,
        "can_delete": True,
    }

@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_committee_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Eliminar una reunión de comité y todo su flujo asociado"""
    meeting = db.query(CommitteeMeeting).filter(CommitteeMeeting.id == meeting_id).first()

    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reunión no encontrada"
        )

    # Eliminar actividades/compromisos vinculados a esta reunión
    db.query(CommitteeActivity).filter(
        CommitteeActivity.meeting_id == meeting_id
    ).delete()

    # Eliminar registros de asistencia asociados
    db.query(MeetingAttendance).filter(
        MeetingAttendance.meeting_id == meeting_id
    ).delete()

    db.delete(meeting)
    db.commit()

@router.post("/{meeting_id}/start", response_model=CommitteeMeetingSchema)
async def start_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Iniciar una reunión"""
    meeting = db.query(CommitteeMeeting).filter(CommitteeMeeting.id == meeting_id).first()
    
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reunión no encontrada"
        )
    
    if meeting.status != "scheduled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se pueden iniciar reuniones programadas"
        )
    
    meeting.status = "in_progress"
    meeting.actual_start_time = datetime.now()
    
    db.commit()
    db.refresh(meeting)
    
    return meeting

@router.post("/{meeting_id}/complete", response_model=CommitteeMeetingSchema)
async def complete_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Completar una reunión"""
    meeting = db.query(CommitteeMeeting).filter(CommitteeMeeting.id == meeting_id).first()
    
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reunión no encontrada"
        )
    
    if meeting.status != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se pueden completar reuniones en progreso"
        )
    
    meeting.status = "completed"
    meeting.actual_end_time = datetime.now()
    
    db.commit()
    db.refresh(meeting)
    
    return meeting

@router.post("/{meeting_id}/cancel", response_model=CommitteeMeetingSchema)
async def cancel_meeting(
    meeting_id: int,
    body: dict = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cancelar una reunión con motivo opcional"""
    meeting = db.query(CommitteeMeeting).filter(CommitteeMeeting.id == meeting_id).first()

    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reunión no encontrada"
        )

    if meeting.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede cancelar una reunión completada"
        )

    meeting.status = "cancelled"

    # Guardar el motivo de cancelación en las notas
    reason = (body or {}).get("reason", "")
    if reason:
        cancel_note = f"Motivo de cancelación: {reason}"
        meeting.notes = f"{meeting.notes}\n\n{cancel_note}" if meeting.notes else cancel_note

    db.commit()
    db.refresh(meeting)

    return meeting

# Meeting Attendance endpoints
@router.get("/{meeting_id}/attendance", response_model=List[MeetingAttendanceSchema])
async def get_meeting_attendance(
    meeting_id: int,
    status: Optional[AttendanceStatusEnum] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener la asistencia de una reunión"""
    # Verificar que la reunión existe
    meeting = db.query(CommitteeMeeting).filter(CommitteeMeeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reunión no encontrada"
        )
    
    query = db.query(MeetingAttendance).filter(
        MeetingAttendance.meeting_id == meeting_id
    )
    
    if status:
        query = query.filter(MeetingAttendance.status == status)
    
    attendance = query.all()
    
    return attendance

@router.post("/{meeting_id}/attendance", response_model=MeetingAttendanceSchema, status_code=status.HTTP_201_CREATED)
async def create_meeting_attendance(
    meeting_id: int,
    attendance: MeetingAttendanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Registrar asistencia a una reunión"""
    # Verificar que la reunión existe
    meeting = db.query(CommitteeMeeting).filter(CommitteeMeeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reunión no encontrada"
        )
    
    # Verificar que el miembro existe y pertenece al comité
    member = db.query(CommitteeMember).filter(
        and_(
            CommitteeMember.id == attendance.member_id,
            CommitteeMember.committee_id == meeting.committee_id,
            CommitteeMember.is_active == True
        )
    ).first()

    if not member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El miembro no es parte activa del comité"
        )

    # Verificar que no existe ya un registro de asistencia
    existing_attendance = db.query(MeetingAttendance).filter(
        and_(
            MeetingAttendance.meeting_id == meeting_id,
            MeetingAttendance.member_id == attendance.member_id
        )
    ).first()
    
    if existing_attendance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un registro de asistencia para este usuario"
        )
    
    attendance_data = attendance.model_dump()
    attendance_data["meeting_id"] = meeting_id
    # Mapear 'status' del schema a 'attendance_status' del modelo
    if "status" in attendance_data:
        attendance_data["attendance_status"] = attendance_data.pop("status")

    db_attendance = MeetingAttendance(**attendance_data)
    db.add(db_attendance)
    db.commit()
    db.refresh(db_attendance)
    
    return db_attendance

@router.put("/{meeting_id}/attendance/{member_id}", response_model=MeetingAttendanceSchema)
async def update_meeting_attendance(
    meeting_id: int,
    member_id: int,
    attendance_update: MeetingAttendanceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Actualizar la asistencia de un miembro a una reunión"""
    attendance = db.query(MeetingAttendance).filter(
        and_(
            MeetingAttendance.meeting_id == meeting_id,
            MeetingAttendance.member_id == member_id
        )
    ).first()

    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registro de asistencia no encontrado"
        )

    update_data = attendance_update.model_dump(exclude_unset=True)
    # Mapear 'status' del schema a 'attendance_status' del modelo
    if "status" in update_data:
        update_data["attendance_status"] = update_data.pop("status")
    for field, value in update_data.items():
        setattr(attendance, field, value)
    
    db.commit()
    db.refresh(attendance)
    
    return attendance

@router.get("/committee/{committee_id}", response_model=List[CommitteeMeetingSchema])
async def get_meetings_by_committee(
    committee_id: int,
    status: Optional[str] = Query(None),
    upcoming_only: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener todas las reuniones de un comité específico"""
    # Verificar que el comité existe
    committee = db.query(Committee).filter(Committee.id == committee_id).first()
    if not committee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comité no encontrado"
        )
    
    query = db.query(CommitteeMeeting).filter(
        CommitteeMeeting.committee_id == committee_id
    )
    
    if status:
        query = query.filter(CommitteeMeeting.status == status)
    
    if upcoming_only:
        query = query.filter(CommitteeMeeting.meeting_date >= date.today())
    
    query = query.order_by(desc(CommitteeMeeting.meeting_date))
    
    meetings = query.offset(skip).limit(limit).all()
    
    return meetings

@router.get("/{meeting_id}/statistics")
async def get_meeting_statistics(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener estadísticas de asistencia de una reunión"""
    # Verificar que la reunión existe
    meeting = db.query(CommitteeMeeting).filter(CommitteeMeeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reunión no encontrada"
        )
    
    # Contar asistencias por estado
    attendance_stats = db.query(
        MeetingAttendance.status,
        func.count(MeetingAttendance.id).label('count')
    ).filter(
        MeetingAttendance.meeting_id == meeting_id
    ).group_by(MeetingAttendance.status).all()
    
    # Total de miembros del comité
    total_members = db.query(CommitteeMember).filter(
        and_(
            CommitteeMember.committee_id == meeting.committee_id,
            CommitteeMember.is_active == True
        )
    ).count()
    
    stats = {
        "meeting_id": meeting_id,
        "total_members": total_members,
        "attendance_by_status": {stat.status.value: stat.count for stat in attendance_stats},
        "attendance_rate": 0
    }
    
    # Calcular tasa de asistencia
    present_count = stats["attendance_by_status"].get("present", 0)
    if total_members > 0:
        stats["attendance_rate"] = round((present_count / total_members) * 100, 2)

    return stats


@router.get("/{meeting_id}/minutes/pdf")
async def generate_meeting_minutes_pdf(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generar PDF del Acta de Reunión"""
    # Cargar reunión con relaciones
    meeting = db.query(CommitteeMeeting).options(
        joinedload(CommitteeMeeting.committee),
        joinedload(CommitteeMeeting.attendances).joinedload(MeetingAttendance.member).joinedload(CommitteeMember.user),
    ).filter(CommitteeMeeting.id == meeting_id).first()

    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reunión no encontrada"
        )

    committee = meeting.committee

    # Calcular número de acta (secuencial por comité)
    meeting_count = db.query(CommitteeMeeting).filter(
        and_(
            CommitteeMeeting.committee_id == committee.id,
            CommitteeMeeting.id <= meeting_id,
        )
    ).count()

    # Obtener miembros activos del comité con usuarios
    active_members = db.query(CommitteeMember).options(
        joinedload(CommitteeMember.user)
    ).filter(
        and_(
            CommitteeMember.committee_id == committee.id,
            CommitteeMember.is_active == True
        )
    ).all()

    # Mapeo de roles a español
    role_display = {
        "PRESIDENT": "Presidente",
        "VICE_PRESIDENT": "Vicepresidente",
        "SECRETARY": "Secretario(a)",
        "MEMBER": "Miembro",
        "ALTERNATE": "Suplente",
    }

    # Construir lista de asistentes
    attendance_map = {}
    for att in meeting.attendances:
        attendance_map[att.member_id] = att

    attendees = []
    president_name = "_______________"
    secretary_name = "_______________"

    for member in active_members:
        user = member.user
        name = f"{user.first_name} {user.last_name}" if user else f"Usuario #{member.user_id}"
        role_enum = member.role.value if hasattr(member.role, 'value') else str(member.role)
        role_label = role_display.get(role_enum, role_enum)

        att = attendance_map.get(member.id)
        att_status = att.attendance_status if att else "absent"
        is_present = att_status.upper() in ("PRESENT", "LATE")

        attendees.append({
            "name": name,
            "role": role_label,
            "present": is_present,
        })

        if role_enum == "PRESIDENT":
            president_name = name
        elif role_enum == "SECRETARY":
            secretary_name = name

    # Calcular quórum
    present_count = sum(1 for a in attendees if a["present"])
    total_members_count = len(active_members)
    quorum_pct = round((present_count / total_members_count * 100), 1) if total_members_count > 0 else 0
    quorum_achieved = quorum_pct >= float(committee.quorum_percentage or 50)

    # Reunión anterior (para lectura del acta anterior)
    previous_meeting = db.query(CommitteeMeeting).filter(
        and_(
            CommitteeMeeting.committee_id == committee.id,
            CommitteeMeeting.id < meeting_id,
        )
    ).order_by(desc(CommitteeMeeting.meeting_date)).first()

    previous_acta_number = 0
    previous_meeting_date = ""
    if previous_meeting:
        previous_acta_number = db.query(CommitteeMeeting).filter(
            and_(
                CommitteeMeeting.committee_id == committee.id,
                CommitteeMeeting.id <= previous_meeting.id,
            )
        ).count()
        previous_meeting_date = previous_meeting.meeting_date.strftime("%d/%m/%Y") if previous_meeting.meeting_date else ""

    # Mapeo de estados a español
    status_display = {
        "PENDING": "Pendiente",
        "IN_PROGRESS": "En Progreso",
        "COMPLETED": "Completada",
        "CANCELLED": "Cancelada",
        "OVERDUE": "Vencida",
    }

    # Actividades del acta anterior (compromisos asignados en la reunión anterior)
    previous_activities = []
    if previous_meeting:
        previous_activities_raw = db.query(CommitteeActivity).options(
            joinedload(CommitteeActivity.assigned_member).joinedload(CommitteeMember.user)
        ).filter(
            CommitteeActivity.meeting_id == previous_meeting.id
        ).order_by(CommitteeActivity.due_date).all()

        for act in previous_activities_raw:
            responsible = "Sin asignar"
            if act.assigned_member and act.assigned_member.user:
                u = act.assigned_member.user
                responsible = f"{u.first_name} {u.last_name}"
            act_status = act.status.value if hasattr(act.status, 'value') else str(act.status)
            previous_activities.append({
                "title": act.title or "",
                "responsible": responsible,
                "progress": act.progress_percentage or 0,
                "due_date": act.due_date.strftime("%d/%m/%Y") if act.due_date else "Sin fecha",
                "status": status_display.get(act_status.upper(), act_status),
                "observations": act.notes or "",
            })

    # Actividades asignadas en esta reunión (compromisos nuevos)
    new_activities_raw = db.query(CommitteeActivity).options(
        joinedload(CommitteeActivity.assigned_member).joinedload(CommitteeMember.user)
    ).filter(
        CommitteeActivity.meeting_id == meeting_id
    ).order_by(CommitteeActivity.due_date).all()

    new_activities = []
    for act in new_activities_raw:
        responsible = "Sin asignar"
        if act.assigned_member and act.assigned_member.user:
            u = act.assigned_member.user
            responsible = f"{u.first_name} {u.last_name}"
        new_activities.append({
            "title": act.title or "",
            "responsible": responsible,
            "due_date": act.due_date.strftime("%d/%m/%Y") if act.due_date else "Sin fecha",
            "observations": act.notes or "",
        })

    # Calcular horarios
    meeting_dt = meeting.meeting_date
    start_time = meeting_dt.strftime("%H:%M") if meeting_dt else ""
    duration = meeting.duration_minutes or 60
    end_dt = meeting_dt + timedelta(minutes=duration) if meeting_dt else None
    end_time = end_dt.strftime("%H:%M") if end_dt else ""

    # Filas vacías para completar la tabla a mínimo 8 filas
    empty_rows = max(0, 8 - len(attendees))

    # Preparar datos para el template
    template_data = {
        "acta_number": meeting_count,
        "committee_type": committee.committee_type.value if hasattr(committee.committee_type, 'value') else str(committee.committee_type),
        "committee_name": committee.name,
        "meeting_date": meeting_dt.strftime("%d/%m/%Y") if meeting_dt else "",
        "location": meeting.location or "No especificado",
        "start_time": start_time,
        "end_time": end_time,
        "attendees": attendees,
        "empty_rows": empty_rows,
        "guests": [],
        "quorum_achieved": quorum_achieved,
        "present_count": present_count,
        "total_members": total_members_count,
        "quorum_percentage": str(quorum_pct),
        "previous_meeting": previous_meeting is not None,
        "previous_acta_number": previous_acta_number,
        "previous_meeting_date": previous_meeting_date,
        "agenda": meeting.agenda or "",
        "minutes_content": meeting.minutes_content or "",
        "previous_activities": previous_activities,
        "new_activities": new_activities,
        "notes": meeting.notes or "",
        "secretary_name": secretary_name,
        "president_name": president_name,
    }

    # Generar PDF
    try:
        converter = HTMLToPDFConverter()
        pdf_content = converter.generate_meeting_minutes_pdf(template_data)

        if isinstance(pdf_content, str):
            # Si retorna una ruta, leer el archivo
            with open(pdf_content, "rb") as f:
                pdf_content = f.read()

        filename = f"Acta_Reunion_{meeting_count}_{committee.name.replace(' ', '_')}.pdf"

        return StreamingResponse(
            io.BytesIO(pdf_content),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(pdf_content)),
            }
        )
    except Exception as e:
        logger.error(f"Error generando PDF de acta: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al generar el PDF del acta: {str(e)}"
        )