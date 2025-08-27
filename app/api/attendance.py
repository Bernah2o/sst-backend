from typing import Any, List
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
import os
import io
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from app.dependencies import get_current_active_user
from app.database import get_db
from app.models.user import User
from app.models.attendance import Attendance, AttendanceStatus, AttendanceType
from app.models.course import Course
from app.models.session import Session as SessionModel
from app.schemas.attendance import (
    AttendanceCreate, AttendanceUpdate, AttendanceResponse,
    AttendanceListResponse, AttendanceSummary, CourseAttendanceSummary,
    BulkAttendanceCreate, BulkAttendanceResponse, AttendanceNotificationData
)
from app.schemas.session import (
    SessionCreate, SessionUpdate, SessionResponse, SessionListResponse
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
    course_id: int = None,
    is_active: bool = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get sessions with optional filtering
    """
    query = db.query(SessionModel)
    
    if course_id:
        query = query.filter(SessionModel.course_id == course_id)
    
    if is_active is not None:
        query = query.filter(SessionModel.is_active == is_active)
    
    # Order by session date and start time
    query = query.order_by(SessionModel.session_date.desc(), SessionModel.start_time.desc())
    
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
            "course": {
                "id": course.id,
                "title": course.title,
                "type": course.course_type.value if course.course_type else None
            } if course else None
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
        has_prev=has_prev
    )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get session by ID
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
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
        "course": {
            "id": course.id,
            "title": course.title,
            "type": course.course_type.value if course.course_type else None
        } if course else None
    }
    
    return response_data


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    session_data: SessionCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Create new session (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Check if course exists
    course = db.query(Course).filter(Course.id == session_data.course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
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
            "type": course.course_type.value if course.course_type else None
        }
    }
    
    return response_data


@router.put("/sessions/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: int,
    session_data: SessionUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Update session (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
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
        "course": {
            "id": course.id,
            "title": course.title,
            "type": course.course_type.value if course.course_type else None
        } if course else None
    }
    
    return response_data


@router.delete("/sessions/{session_id}", response_model=MessageResponse)
async def delete_session(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Delete session (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    db.delete(session)
    db.commit()
    
    return MessageResponse(message="Session deleted successfully")


# Attendance endpoints
@router.get("/", response_model=PaginatedResponse[AttendanceListResponse])
async def get_attendance_records(
    skip: int = 0,
    limit: int = 100,
    user_id: int = None,
    course_id: int = None,
    session_date: date = None,
    status: AttendanceStatus = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get attendance records with optional filtering
    """
    query = db.query(Attendance)
    
    # Apply filters
    if user_id:
        # Users can only see their own attendance unless they are admin or capacitador
        if current_user.role.value not in ["admin", "capacitador"] and current_user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        query = query.filter(Attendance.user_id == user_id)
    elif current_user.role.value not in ["admin", "capacitador"]:
        # Non-admin/capacitador users can only see their own attendance
        query = query.filter(Attendance.user_id == current_user.id)
    
    if course_id:
        query = query.filter(Attendance.course_id == course_id)
    
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
        # Get user information
        user = db.query(User).filter(User.id == record.user_id).first()
        # Get course information
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
            "user": {
                "id": user.id,
                "name": user.full_name,
                "email": user.email
            } if user else None,
            "course": {
                "id": course.id,
                "title": course.title
            } if course else None
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
        has_prev=has_prev
    )


@router.post("/", response_model=AttendanceResponse)
async def create_attendance_record(
    attendance_data: AttendanceCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Create new attendance record
    """
    # Check if course exists
    course = db.query(Course).filter(Course.id == attendance_data.course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Users can only create attendance for themselves unless they are admin or capacitador
    if current_user.role.value not in ["admin", "capacitador"] and attendance_data.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Check if attendance record already exists for this user, course, and date
    existing_attendance = db.query(Attendance).filter(
        and_(
            Attendance.user_id == attendance_data.user_id,
            Attendance.course_id == attendance_data.course_id,
            func.date(Attendance.session_date) == func.date(attendance_data.session_date)
        )
    ).first()
    
    if existing_attendance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Attendance record already exists for this date"
        )
    
    # Create new attendance record
    attendance = Attendance(**attendance_data.dict())
    
    db.add(attendance)
    db.commit()
    db.refresh(attendance)
    
    return attendance


@router.get("/stats")
async def get_attendance_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get attendance statistics by status
    """
    # Check permissions
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Get counts by status
    stats_query = db.query(
        Attendance.status,
        func.count(Attendance.id).label('count')
    ).group_by(Attendance.status).all()
    
    # Initialize stats with default values
    stats = {
        "total_attendance": 0,
        "present": 0,
        "absent": 0,
        "late": 0,
        "excused": 0,
        "partial": 0
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


@router.get("/{attendance_id}", response_model=AttendanceResponse)
async def get_attendance_record(
    attendance_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get attendance record by ID
    """
    attendance = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    
    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance record not found"
        )
    
    # Users can only see their own attendance unless they are admin or capacitador
    if current_user.role.value not in ["admin", "capacitador"] and attendance.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    return attendance


@router.put("/{attendance_id}", response_model=AttendanceResponse)
async def update_attendance_record(
    attendance_id: int,
    attendance_data: AttendanceUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Update attendance record
    """
    attendance = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    
    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance record not found"
        )
    
    # Users can only update their own attendance unless they are admin or capacitador
    if current_user.role.value not in ["admin", "capacitador"] and attendance.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Update attendance fields
    update_data = attendance_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(attendance, field, value)
    
    db.commit()
    db.refresh(attendance)
    
    return attendance


@router.delete("/{attendance_id}", response_model=MessageResponse)
async def delete_attendance_record(
    attendance_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Delete attendance record (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    attendance = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    
    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance record not found"
        )
    
    db.delete(attendance)
    db.commit()
    
    return MessageResponse(message="Attendance record deleted successfully")


@router.post("/check-in", response_model=AttendanceResponse)
async def check_in(
    course_id: int,
    location: str = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Check in to a course session
    """
    # Check if course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Check if user already checked in today
    today = datetime.now().date()
    existing_attendance = db.query(Attendance).filter(
        and_(
            Attendance.user_id == current_user.id,
            Attendance.course_id == course_id,
            func.date(Attendance.session_date) == today
        )
    ).first()
    
    if existing_attendance:
        if existing_attendance.check_in_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Already checked in for today"
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
        location=location
    )
    
    db.add(attendance)
    db.commit()
    db.refresh(attendance)
    
    return attendance


@router.post("/check-out/{attendance_id}", response_model=AttendanceResponse)
async def check_out(
    attendance_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Check out from a course session
    """
    attendance = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    
    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance record not found"
        )
    
    # Users can only check out their own attendance
    if attendance.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    if not attendance.check_in_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must check in before checking out"
        )
    
    if attendance.check_out_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already checked out"
        )
    
    # Update check out time and calculate duration
    attendance.check_out_time = datetime.now()
    duration = attendance.check_out_time - attendance.check_in_time
    attendance.duration_minutes = int(duration.total_seconds() / 60)
    
    # Calculate completion percentage if scheduled duration is set
    if attendance.scheduled_duration_minutes:
        attendance.completion_percentage = min(
            (attendance.duration_minutes / attendance.scheduled_duration_minutes) * 100,
            100.0
        )
    
    db.commit()
    db.refresh(attendance)
    
    return attendance


@router.get("/summary/user/{user_id}", response_model=AttendanceSummary)
async def get_user_attendance_summary(
    user_id: int,
    course_id: int = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get attendance summary for a user
    """
    # Users can only see their own summary unless they are admin or capacitador
    if current_user.role.value not in ["admin", "capacitador"] and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    query = db.query(Attendance).filter(Attendance.user_id == user_id)
    
    if course_id:
        query = query.filter(Attendance.course_id == course_id)
    
    # Get attendance statistics
    total_sessions = query.count()
    present_sessions = query.filter(Attendance.status == AttendanceStatus.PRESENT).count()
    absent_sessions = query.filter(Attendance.status == AttendanceStatus.ABSENT).count()
    late_sessions = query.filter(Attendance.status == AttendanceStatus.LATE).count()
    
    attendance_rate = (present_sessions / total_sessions * 100) if total_sessions > 0 else 0
    
    return AttendanceSummary(
        user_id=user_id,
        course_id=course_id,
        total_sessions=total_sessions,
        present_sessions=present_sessions,
        absent_sessions=absent_sessions,
        late_sessions=late_sessions,
        attendance_rate=attendance_rate
    )


@router.get("/summary/course/{course_id}", response_model=CourseAttendanceSummary)
async def get_course_attendance_summary(
    course_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get attendance summary for a course (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Check if course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    query = db.query(Attendance).filter(Attendance.course_id == course_id)
    
    # Get attendance statistics
    total_sessions = query.count()
    present_sessions = query.filter(Attendance.status == AttendanceStatus.PRESENT).count()
    absent_sessions = query.filter(Attendance.status == AttendanceStatus.ABSENT).count()
    late_sessions = query.filter(Attendance.status == AttendanceStatus.LATE).count()
    
    # Get unique students count
    unique_students = query.distinct(Attendance.user_id).count()
    
    average_attendance_rate = (present_sessions / total_sessions * 100) if total_sessions > 0 else 0
    
    return CourseAttendanceSummary(
        course_id=course_id,
        total_sessions=total_sessions,
        present_sessions=present_sessions,
        absent_sessions=absent_sessions,
        late_sessions=late_sessions,
        unique_students=unique_students,
        average_attendance_rate=average_attendance_rate
    )





@router.delete("/sessions/{session_id}", response_model=MessageResponse)
async def delete_session(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Delete session (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    db.delete(session)
    db.commit()
    
    return MessageResponse(message="Session deleted successfully")


@router.post("/bulk-register", response_model=BulkAttendanceResponse)
async def bulk_register_attendance(
    bulk_data: BulkAttendanceCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Register attendance for multiple users in a session with email notifications
    (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Check if session exists
    session = db.query(SessionModel).filter(SessionModel.id == bulk_data.session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Get course information
    course = db.query(Course).filter(Course.id == session.course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
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
            enrollment = db.query(Enrollment).filter(
                and_(Enrollment.user_id == user_id, Enrollment.course_id == course.id)
            ).first()
            if not enrollment:
                errors.append(f"User {user.username} is not enrolled in course {course.title}")
                failed_registrations += 1
                continue
            
            # Check if attendance record already exists
            existing_attendance = db.query(Attendance).filter(
                and_(
                    Attendance.user_id == user_id,
                    Attendance.session_id == bulk_data.session_id
                )
            ).first()
            
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
                    session_date=datetime.combine(session.session_date, session.start_time),
                    status=bulk_data.status,
                    attendance_type=bulk_data.attendance_type,
                    check_in_time=datetime.now() if bulk_data.status == AttendanceStatus.PRESENT else None,
                    location=bulk_data.location,
                    notes=bulk_data.notes,
                    verified_by=current_user.id,
                    verified_at=datetime.now()
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
                        status=bulk_data.status.value
                    )
                    
                    # Create notification message
                    status_text = {
                        "present": "presente",
                        "absent": "ausente",
                        "late": "tardanza",
                        "excused": "justificado",
                        "partial": "parcial"
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
                        created_by=current_user.id
                    )
                    db.add(notification)
                    notifications_sent += 1
                    
                except Exception as e:
                    errors.append(f"Failed to send notification to {user.email}: {str(e)}")
            
        except Exception as e:
            errors.append(f"Error processing user {user_id}: {str(e)}")
            failed_registrations += 1
    
    # Commit all changes
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save attendance records: {str(e)}"
        )
    
    return BulkAttendanceResponse(
        session_id=bulk_data.session_id,
        total_users=len(bulk_data.user_ids),
        successful_registrations=successful_registrations,
        failed_registrations=failed_registrations,
        notifications_sent=notifications_sent,
        errors=errors
    )


@router.get("/sessions/{session_id}/attendance-list")
async def generate_attendance_list_pdf(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> FileResponse:
    """
    Generate attendance list PDF for a session (admin and capacitador roles only)
    """
    if current_user.role.value not in ["admin", "capacitador"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Check if session exists
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Get course information
    course = db.query(Course).filter(Course.id == session.course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Get enrolled users for this course
    enrolled_users_query = db.query(User).join(Enrollment).filter(
        Enrollment.course_id == course.id
    )
    
    # Filter out users who are marked as absent for this specific session
    # Get attendance records for this session
    absent_user_ids = db.query(Attendance.user_id).filter(
        and_(
            Attendance.session_id == session_id,
            Attendance.status == AttendanceStatus.ABSENT
        )
    ).subquery()
    
    # Exclude absent users from the list
    enrolled_users = enrolled_users_query.filter(
        ~User.id.in_(absent_user_ids)
    ).order_by(User.first_name, User.last_name).all()
    
    if not enrolled_users:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No enrolled users found for this course or all users are marked as absent"
        )
    
    # Create PDF
    try:
        # Create attendance_lists directory if it doesn't exist
        attendance_dir = "attendance_lists"
        if not os.path.exists(attendance_dir):
            os.makedirs(attendance_dir)
        
        # Generate filename
        filename = f"lista_asistencia_sesion_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(attendance_dir, filename)
        
        # Create PDF document with margins
        doc = SimpleDocTemplate(
            filepath, 
            pagesize=A4,
            rightMargin=50,
            leftMargin=50,
            topMargin=50,
            bottomMargin=50
        )
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles with corporate colors
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=20,
            spaceAfter=20,
            spaceBefore=10,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#1976d2'),  # Blue corporate color
            fontName='Helvetica-Bold'
        )
        
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=25,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#424242'),  # Dark gray
            fontName='Helvetica'
        )
        
        header_style = ParagraphStyle(
            'CustomHeader',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=8,
            spaceBefore=2,
            alignment=TA_LEFT,
            textColor=colors.HexColor('#333333'),
            fontName='Helvetica'
        )
        
        info_box_style = ParagraphStyle(
            'InfoBox',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=5,
            spaceBefore=2,
            alignment=TA_LEFT,
            textColor=colors.HexColor('#555555'),
            fontName='Helvetica',
            leftIndent=10,
            rightIndent=10
        )
        
        # Header with company/system name
        company_header = Paragraph(
            "<b>SISTEMA DE GESTIÓN DE CAPACITACIÓN</b>", 
            ParagraphStyle(
                'CompanyHeader',
                parent=styles['Normal'],
                fontSize=12,
                alignment=TA_CENTER,
                textColor=colors.HexColor('#666666'),
                spaceAfter=10
            )
        )
        story.append(company_header)
        
        # Decorative line
        from reportlab.platypus import HRFlowable
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#1976d2')))
        story.append(Spacer(1, 15))
        
        # Title
        title = Paragraph("LISTA DE ASISTENCIA", title_style)
        story.append(title)
        
        # Subtitle with session info
        subtitle = Paragraph(f"Sesión: {session.title}", subtitle_style)
        story.append(subtitle)
        story.append(Spacer(1, 20))
        
        # Session information in a styled box
        info_table_data = [
            ["Curso:", course.title],
            ["Fecha:", session.session_date.strftime('%d de %B de %Y')],
            ["Horario:", f"{session.start_time.strftime('%H:%M')} - {session.end_time.strftime('%H:%M')}"],
            ["Ubicación:", session.location or 'No especificada'],
            ["Total Inscritos:", str(len(enrolled_users))]
        ]
        
        info_table = Table(info_table_data, colWidths=[1.5*inch, 4*inch])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f5f5f5')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1976d2')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        story.append(info_table)
        story.append(Spacer(1, 25))
        
        # Instructions
        instructions = Paragraph(
            "<b>Instrucciones:</b> Por favor firme en la columna correspondiente para confirmar su asistencia.",
            ParagraphStyle(
                'Instructions',
                parent=styles['Normal'],
                fontSize=9,
                alignment=TA_CENTER,
                textColor=colors.HexColor('#666666'),
                spaceAfter=15,
                fontName='Helvetica-Oblique'
            )
        )
        story.append(instructions)
        
        # Create table data
        table_data = []
        # Header row
        table_data.append(['N°', 'Nombre Completo', 'Email', 'Firma'])
        
        # Add enrolled users
        for i, user in enumerate(enrolled_users, 1):
            table_data.append([
                str(i),
                user.full_name or user.username,
                user.email,
                ''  # Empty space for signature
            ])
        
        # Create table with improved column widths
        table = Table(table_data, colWidths=[0.6*inch, 2.8*inch, 2.2*inch, 1.8*inch])
        
        # Enhanced table style
        table.setStyle(TableStyle([
            # Header row style with corporate colors
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            
            # Data rows style
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Number column centered
            ('ALIGN', (1, 1), (2, -1), 'LEFT'),    # Name and email left aligned
            ('ALIGN', (3, 1), (3, -1), 'CENTER'),  # Signature column centered
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            
            # Padding for better spacing
            ('LEFTPADDING', (0, 1), (-1, -1), 8),
            ('RIGHTPADDING', (0, 1), (-1, -1), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 12),
            
            # Alternating row colors for better readability
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            
            # Grid and borders with subtle colors
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor('#1976d2')),
            
            # Special styling for signature column
            ('BACKGROUND', (3, 0), (3, 0), colors.HexColor('#1565c0')),  # Darker blue for signature header
            ('GRID', (3, 1), (3, -1), 1, colors.HexColor('#e3f2fd')),  # Light blue grid for signature column
        ]))
        
        # Set minimum row height for signature space (increased for better usability)
        for i in range(1, len(table_data)):
            table._argH[i] = 0.75*inch  # Increased height for signatures
        
        story.append(table)
        
        # Add spacing and additional information
        story.append(Spacer(1, 25))
        
        # Summary section
        summary_data = [
            ["Total de participantes:", str(len(enrolled_users))],
            ["Presentes:", "_____"],
            ["Ausentes:", "_____"],
            ["Observaciones:", ""]
        ]
        
        summary_table = Table(summary_data, colWidths=[1.5*inch, 2*inch])
        summary_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -2), 0.5, colors.HexColor('#dee2e6')),
            ('SPAN', (1, -1), (1, -1)),  # Span for observations
            ('LINEBELOW', (1, -1), (1, -1), 0.5, colors.HexColor('#dee2e6')),
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 30))
        
        # Signature section for instructor/supervisor
        signature_section = Table([
            ["Firma del Instructor/Capacitador:", "", "Fecha:", ""]
        ], colWidths=[2*inch, 2*inch, 1*inch, 1.5*inch])
        
        signature_section.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (2, 0), (2, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
            ('LINEBELOW', (1, 0), (1, 0), 1, colors.black),
            ('LINEBELOW', (3, 0), (3, 0), 1, colors.black),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 20),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        
        story.append(signature_section)
        story.append(Spacer(1, 20))
        
        # Footer with generation info
        footer_line = HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e0e0e0'))
        story.append(footer_line)
        story.append(Spacer(1, 10))
        
        footer_text = f"Documento generado el {datetime.now().strftime('%d de %B de %Y a las %H:%M')} por {current_user.full_name or current_user.username}"
        footer = Paragraph(
            footer_text, 
            ParagraphStyle(
                'Footer',
                parent=styles['Normal'],
                fontSize=8,
                alignment=TA_CENTER,
                textColor=colors.HexColor('#888888'),
                fontName='Helvetica-Oblique'
            )
        )
        story.append(footer)
        
        # Add page number functionality
        def add_page_number(canvas, doc):
            canvas.saveState()
            canvas.setFont('Helvetica', 8)
            canvas.setFillColor(colors.HexColor('#888888'))
            page_num = canvas.getPageNumber()
            text = f"Página {page_num}"
            canvas.drawRightString(A4[0] - 50, 30, text)
            canvas.restoreState()
        
        # Build PDF with page numbers
        doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
        
        # Return file
        return FileResponse(
            path=filepath,
            filename=f"lista_asistencia_{session.title.replace(' ', '_')}_{session.session_date.strftime('%Y%m%d')}.pdf",
            media_type='application/pdf'
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating attendance list PDF: {str(e)}"
        )
