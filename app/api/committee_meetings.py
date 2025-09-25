"""
API endpoints for Committee Meetings Management
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc, asc, func
from datetime import datetime, date

from app.database import get_db
from app.dependencies import get_current_user
from app.models.committee import (
    Committee, CommitteeMeeting, MeetingAttendance, CommitteeMember
)
from app.models.user import User
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
            user_id=member.user_id,
            status=AttendanceStatusEnum.pending
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

@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_committee_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Eliminar una reunión de comité"""
    meeting = db.query(CommitteeMeeting).filter(CommitteeMeeting.id == meeting_id).first()
    
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reunión no encontrada"
        )
    
    # Verificar que no se pueda eliminar una reunión completada
    if meeting.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar una reunión completada"
        )
    
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cancelar una reunión"""
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
    
    # Verificar que el usuario es miembro del comité
    member = db.query(CommitteeMember).filter(
        and_(
            CommitteeMember.committee_id == meeting.committee_id,
            CommitteeMember.user_id == attendance.user_id,
            CommitteeMember.is_active == True
        )
    ).first()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario no es miembro activo del comité"
        )
    
    # Verificar que no existe ya un registro de asistencia
    existing_attendance = db.query(MeetingAttendance).filter(
        and_(
            MeetingAttendance.meeting_id == meeting_id,
            MeetingAttendance.user_id == attendance.user_id
        )
    ).first()
    
    if existing_attendance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un registro de asistencia para este usuario"
        )
    
    attendance_data = attendance.model_dump()
    attendance_data["meeting_id"] = meeting_id
    
    db_attendance = MeetingAttendance(**attendance_data)
    db.add(db_attendance)
    db.commit()
    db.refresh(db_attendance)
    
    return db_attendance

@router.put("/{meeting_id}/attendance/{user_id}", response_model=MeetingAttendanceSchema)
async def update_meeting_attendance(
    meeting_id: int,
    user_id: int,
    attendance_update: MeetingAttendanceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Actualizar la asistencia de un usuario a una reunión"""
    attendance = db.query(MeetingAttendance).filter(
        and_(
            MeetingAttendance.meeting_id == meeting_id,
            MeetingAttendance.user_id == user_id
        )
    ).first()
    
    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registro de asistencia no encontrado"
        )
    
    update_data = attendance_update.model_dump(exclude_unset=True)
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