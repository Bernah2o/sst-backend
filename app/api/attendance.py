from typing import Any, List
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, status, Response, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
import os
import io
from app.utils.storage import StorageManager
from app.config import settings

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
    attendance_dict = attendance_data.dict()
    
    # Calculate duration automatically if both check_in_time and check_out_time are provided
    if attendance_dict.get('check_in_time') and attendance_dict.get('check_out_time'):
        check_in = attendance_dict['check_in_time']
        check_out = attendance_dict['check_out_time']
        
        # Ensure both are datetime objects
        if isinstance(check_in, str):
            check_in = datetime.fromisoformat(check_in.replace('Z', '+00:00'))
        if isinstance(check_out, str):
            check_out = datetime.fromisoformat(check_out.replace('Z', '+00:00'))
        
        # Calculate duration in minutes
        duration = check_out - check_in
        attendance_dict['duration_minutes'] = int(duration.total_seconds() / 60)
        
        # Set scheduled_duration_minutes to the same value if not provided
        if not attendance_dict.get('scheduled_duration_minutes'):
            attendance_dict['scheduled_duration_minutes'] = attendance_dict['duration_minutes']
        
        # Calculate completion percentage
        if attendance_dict['scheduled_duration_minutes'] and attendance_dict['scheduled_duration_minutes'] > 0:
            attendance_dict['completion_percentage'] = min(100.0, 
                (attendance_dict['duration_minutes'] / attendance_dict['scheduled_duration_minutes']) * 100)
    
    attendance = Attendance(**attendance_dict)
    
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
        if attendance.scheduled_duration_minutes and attendance.scheduled_duration_minutes > 0:
            attendance.completion_percentage = min(100.0, 
                (attendance.duration_minutes / attendance.scheduled_duration_minutes) * 100)
    
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
    download: bool = Query(False, description="Set to true to download the file with a custom filename"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
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
    
    # Create PDF using HTML template
    try:
        # Import HTML to PDF converter
        from app.services.html_to_pdf import HTMLToPDFConverter
        from app.utils.storage import storage_manager
        from app.config import settings
        
        # Generate filename with simple naming to avoid encoding issues
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"reporte_asistencia_{session_id}_{timestamp}.pdf"
        
        # Create attendance_lists directory if it doesn't exist (for local storage)
        attendance_dir = "attendance_lists"
        if not os.path.exists(attendance_dir):
            os.makedirs(attendance_dir)
        
        local_filepath = os.path.join(attendance_dir, filename)
        
        # Initialize HTML to PDF converter
        converter = HTMLToPDFConverter()
        
        # Format date for display
        formatted_date = session.session_date.strftime("%d/%m/%Y") if hasattr(session, 'session_date') else datetime.now().strftime("%d/%m/%Y")
        
        # Prepare attendees data
        attendees_data = [{
            "name": f"{user.first_name} {user.last_name}",
            "document": user.document_number or "N/A",
            "position": user.position or "N/A",
            "area": user.area or "N/A"
        } for user in enrolled_users]
        
        # Prepare session data
        session_data = {
            'title': 'Lista de Asistencia',
            'session_date': formatted_date,
            'course_title': course.title,
            'instructor_name': f"{current_user.first_name} {current_user.last_name}",
            'location': session.location or "No especificado",
            'duration': str(course.duration_hours) if hasattr(course, 'duration_hours') and course.duration_hours else 'N/A',
            'attendance_percentage': 100  # Por defecto 100% para los presentes
        }
        
        # Preparar los datos en el formato esperado por la plantilla
        template_data = {
            "session": session_data,
            "attendees": attendees_data
        }
        
        # Generar el PDF directamente en memoria
        pdf_content = converter.generate_attendance_list_pdf(template_data)
        
        # Nombre de archivo simplificado para evitar problemas de codificación
        safe_filename = f"reporte_asistencia_{session_id}.pdf"
        
        # Determinar si usar Firebase Storage o almacenamiento local
        use_firebase = getattr(settings, 'USE_FIREBASE_STORAGE', 'False').lower() == 'true'
        
        # Ruta en Firebase Storage
        firebase_path = f"attendance_lists/{filename}"
        
        if use_firebase:
            # Subir a Firebase Storage
            storage_manager.upload_file(firebase_path, pdf_content, content_type="application/pdf")
            # Obtener URL pública
            file_url = storage_manager.get_public_url(firebase_path)
            # También guardar localmente para poder usar FileResponse
            with open(local_filepath, "wb") as f:
                f.write(pdf_content)
        else:
            # Guardar el PDF en disco para poder usar FileResponse
            with open(local_filepath, "wb") as f:
                f.write(pdf_content)
            file_url = None
        
        # Preparar parámetros de respuesta
        response_params = {
            "path": local_filepath,
            "media_type": "application/pdf"
        }
        
        # Si se solicita descarga, agregar un nombre de archivo personalizado
        if download:
            # Limpiar nombre del curso para el nombre de archivo
            import re
            clean_course_name = re.sub(r'[^\w\s-]', '', course.title).strip()
            clean_course_name = re.sub(r'[-\s]+', '_', clean_course_name)
            
            # Agregar nombre de archivo a los parámetros de respuesta
            response_params["filename"] = f"Lista_Asistencia_{clean_course_name}_{formatted_date}.pdf"
        
        # Devolver respuesta de archivo con los parámetros apropiados
        return FileResponse(**response_params)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating attendance list PDF: {str(e)}"
        )
