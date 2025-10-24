from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
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