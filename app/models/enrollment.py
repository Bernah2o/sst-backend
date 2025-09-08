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
        self.status = EnrollmentStatus.COMPLETED.value
        self.completed_at = datetime.utcnow()
        self.progress = 100.0
        if grade is not None:
            self.grade = grade
        
        # Trigger automatic reinduction status update if this is a reinduction course
        self._check_and_update_reinduction_status()

    def start_enrollment(self):
        """Start the enrollment"""
        if self.status == EnrollmentStatus.PENDING.value:
            self.status = EnrollmentStatus.ACTIVE.value
            self.started_at = datetime.utcnow()

    def cancel_enrollment(self, reason: str = None):
        """Cancel the enrollment"""
        self.status = EnrollmentStatus.CANCELLED.value
        if reason:
            self.notes = f"Cancelled: {reason}"

    def suspend_enrollment(self, reason: str = None):
        """Suspend the enrollment"""
        self.status = EnrollmentStatus.SUSPENDED.value
        if reason:
            self.notes = f"Suspended: {reason}"

    def update_progress(self, progress: float):
        """Update enrollment progress"""
        self.progress = max(0.0, min(100.0, progress))
        # Note: Enrollment completion is now handled by the course completion logic
        # that considers materials, surveys, and evaluations together
    
    def _check_and_update_reinduction_status(self):
        """Check and update reinduction status when enrollment is completed"""
        from app.models.course import CourseType
        from app.models.reinduction import ReinductionRecord, ReinductionStatus
        from app.database import SessionLocal
        
        # Only process if this is a reinduction course
        if self.course and self.course.course_type == CourseType.REINDUCTION:
            db = SessionLocal()
            try:
                # Find the corresponding reinduction record
                record = db.query(ReinductionRecord).filter(
                    ReinductionRecord.enrollment_id == self.id
                ).first()
                
                if record and record.status != ReinductionStatus.COMPLETED:
                    record.status = ReinductionStatus.COMPLETED
                    record.completed_date = self.completed_at.date() if self.completed_at else datetime.utcnow().date()
                    db.commit()
                    print(f"Reinducción automáticamente marcada como completada para el registro {record.id}")
            except Exception as e:
                print(f"Error actualizando estado de reinducción: {str(e)}")
                db.rollback()
            finally:
                db.close()