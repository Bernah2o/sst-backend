from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    Float,
)
from sqlalchemy.orm import relationship

from app.database import Base


class AttendanceStatus(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"
    PARTIAL = "partial"


class AttendanceType(str, Enum):
    IN_PERSON = "in_person"
    VIRTUAL = "virtual"
    HYBRID = "hybrid"
    SELF_PACED = "self_paced"


class Attendance(Base):
    __tablename__ = "attendances"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_name = Column(String(255), nullable=True)  # Solo texto, no FK
    enrollment_id = Column(Integer, ForeignKey("enrollments.id"), nullable=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=True)
    session_date = Column(DateTime, nullable=False)
    status = Column(SQLEnum(AttendanceStatus), nullable=False)
    attendance_type = Column(SQLEnum(AttendanceType), default=AttendanceType.IN_PERSON)
    check_in_time = Column(DateTime)
    check_out_time = Column(DateTime)
    duration_minutes = Column(Integer)  # Actual time spent
    scheduled_duration_minutes = Column(Integer)  # Expected duration
    completion_percentage = Column(Float, default=0.0)  # For self-paced courses
    location = Column(String(255))  # Physical location or virtual room
    ip_address = Column(String(45))  # For virtual attendance tracking
    device_info = Column(String(255))  # Device used for virtual attendance
    
    # Virtual attendance specific fields
    session_code = Column(String(20))  # Code for virtual session validation
    session_code_used_at = Column(DateTime)  # When the session code was used
    virtual_session_link = Column(String(500))  # Link to virtual meeting
    device_fingerprint = Column(String(255))  # Unique device identifier
    connection_quality = Column(String(50))  # Connection quality reported
    minimum_duration_met = Column(Boolean, default=False)  # If minimum time was met
    facilitator_confirmed = Column(Boolean, default=False)  # Manual confirmation by facilitator
    virtual_evidence = Column(Text)  # Additional evidence for virtual attendance
    browser_info = Column(String(255))  # Browser and OS information
    
    # Employee system time fields
    employee_system_time = Column(DateTime)  # Employee's system time when registering
    employee_local_time = Column(String(50))  # Employee's local time string
    employee_timezone = Column(String(100))  # Employee's timezone
    
    notes = Column(Text)  # Additional notes about attendance
    verified_by = Column(Integer, ForeignKey("users.id"))  # Who verified the attendance
    verified_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="attendances")
    enrollment = relationship("Enrollment", back_populates="attendance_records")
    session = relationship("Session", back_populates="attendances")
    verifier = relationship("User", foreign_keys=[verified_by])

    def __repr__(self):
        return f"<Attendance(id={self.id}, user_id={self.user_id}, status='{self.status}')>"


class VirtualSession(Base):
    __tablename__ = "virtual_sessions"

    id = Column(Integer, primary_key=True, index=True)
    course_name = Column(String(255), nullable=False)
    session_date = Column(DateTime, nullable=False)  # Cambiado de Date a DateTime para incluir hora
    end_date = Column(DateTime, nullable=False)  # Nueva fecha y hora final de la sesión
    virtual_session_link = Column(String(500), nullable=False)
    session_code = Column(String(20), unique=True, nullable=False)
    valid_until = Column(DateTime, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    max_participants = Column(Integer, default=100)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    creator = relationship("User", back_populates="created_virtual_sessions")

    def __repr__(self):
        return f"<VirtualSession(id={self.id}, course_name='{self.course_name}', session_code='{self.session_code}')>"

    @property
    def duration_minutes(self) -> int:
        """Calculate session duration in minutes"""
        if self.session_date and self.end_date:
            # Asegurarse que ambos sean datetime
            start = self.session_date
            end = self.end_date
            if isinstance(start, datetime) and isinstance(end, datetime):
                delta = end - start
                return int(delta.total_seconds() / 60)
            # Si alguno es date, convertir a datetime
            if not isinstance(start, datetime):
                start = datetime.combine(start, datetime.min.time())
            if not isinstance(end, datetime):
                end = datetime.combine(end, datetime.min.time())
            delta = end - start
            return int(delta.total_seconds() / 60)
        return 0

    @property
    def is_session_active(self) -> bool:
        """Check if session is currently active based on current time"""
        now = datetime.utcnow()
        start = self.session_date
        end = self.end_date
        # Convert to datetime if needed
        if not isinstance(start, datetime):
            start = datetime.combine(start, datetime.min.time())
        if not isinstance(end, datetime):
            end = datetime.combine(end, datetime.min.time())
        return start <= now <= end and self.is_active

    @property
    def is_session_expired(self) -> bool:
        """Check if session has expired"""
        now = datetime.utcnow()
        return now > self.end_date

    @property
    def attendance_percentage(self) -> float:
        """Calculate attendance percentage based on duration"""
        if not self.duration_minutes or not self.scheduled_duration_minutes:
            return 0.0

        percentage = (self.duration_minutes / self.scheduled_duration_minutes) * 100
        return min(percentage, 100.0)  # Cap at 100%

    def is_present(self) -> bool:
        """Check if user was present (including late and partial)"""
        return self.status in [
            AttendanceStatus.PRESENT,
            AttendanceStatus.LATE,
            AttendanceStatus.PARTIAL,
        ]

    def meets_minimum_attendance(self, minimum_percentage: float = 80.0) -> bool:
        """Check if attendance meets minimum requirement"""
        return self.attendance_percentage >= minimum_percentage