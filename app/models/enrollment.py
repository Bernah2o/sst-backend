from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float
from sqlalchemy.orm import relationship

from app.database import Base


class EnrollmentStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    SUSPENDED = "suspended"


class Enrollment(Base):
    __tablename__ = "enrollments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    status = Column(String(20), default=EnrollmentStatus.PENDING, nullable=False)
    enrolled_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    progress = Column(Float, default=0.0, nullable=False)  # Progress percentage (0-100)
    grade = Column(Float, nullable=True)  # Final grade
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="enrollments")
    course = relationship("Course", back_populates="enrollments")
    attendance_records = relationship("Attendance", back_populates="enrollment")
    
    # Progress relationships
    material_progress = relationship("UserMaterialProgress", back_populates="enrollment")
    module_progress = relationship("UserModuleProgress", back_populates="enrollment")

    def __repr__(self):
        return f"<Enrollment(id={self.id}, user_id={self.user_id}, course_id={self.course_id}, status={self.status})>"

    @property
    def is_active(self) -> bool:
        """Check if enrollment is active"""
        return self.status == EnrollmentStatus.ACTIVE

    @property
    def is_completed(self) -> bool:
        """Check if enrollment is completed"""
        return self.status == EnrollmentStatus.COMPLETED

    @property
    def duration_days(self) -> int:
        """Get enrollment duration in days"""
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).days
        elif self.started_at:
            return (datetime.utcnow() - self.started_at).days
        return 0

    def complete_enrollment(self, grade: float = None):
        """Mark enrollment as completed"""
        self.status = EnrollmentStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.progress = 100.0
        if grade is not None:
            self.grade = grade

    def start_enrollment(self):
        """Start the enrollment"""
        if self.status == EnrollmentStatus.PENDING:
            self.status = EnrollmentStatus.ACTIVE
            self.started_at = datetime.utcnow()

    def cancel_enrollment(self, reason: str = None):
        """Cancel the enrollment"""
        self.status = EnrollmentStatus.CANCELLED
        if reason:
            self.notes = f"Cancelled: {reason}"

    def suspend_enrollment(self, reason: str = None):
        """Suspend the enrollment"""
        self.status = EnrollmentStatus.SUSPENDED
        if reason:
            self.notes = f"Suspended: {reason}"

    def update_progress(self, progress: float):
        """Update enrollment progress"""
        self.progress = max(0.0, min(100.0, progress))
        if self.progress >= 100.0 and self.status == EnrollmentStatus.ACTIVE:
            self.complete_enrollment()