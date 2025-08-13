from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, Boolean
from sqlalchemy.orm import relationship

from app.database import Base


class MaterialProgressStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class UserMaterialProgress(Base):
    """Track user progress for individual course materials"""
    __tablename__ = "user_material_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    enrollment_id = Column(Integer, ForeignKey("enrollments.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("course_materials.id"), nullable=False)
    status = Column(String(20), default=MaterialProgressStatus.NOT_STARTED, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    time_spent_seconds = Column(Integer, default=0)  # Time spent on this material
    progress_percentage = Column(Float, default=0.0)  # For videos/documents with partial progress
    last_position = Column(Integer, default=0)  # For videos: last watched position in seconds
    attempts = Column(Integer, default=0)  # Number of times accessed
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User")
    enrollment = relationship("Enrollment")
    material = relationship("CourseMaterial")

    def __repr__(self):
        return f"<UserMaterialProgress(id={self.id}, user_id={self.user_id}, material_id={self.material_id}, status={self.status})>"

    def start_material(self):
        """Mark material as started"""
        if self.status == MaterialProgressStatus.NOT_STARTED:
            self.status = MaterialProgressStatus.IN_PROGRESS
            self.started_at = datetime.utcnow()
            self.attempts += 1

    def complete_material(self):
        """Mark material as completed"""
        self.status = MaterialProgressStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.progress_percentage = 100.0

    def update_progress(self, percentage: float, position: int = None, time_spent: int = None):
        """Update material progress"""
        self.progress_percentage = max(0.0, min(100.0, percentage))
        if position is not None:
            self.last_position = position
        if time_spent is not None:
            self.time_spent_seconds += time_spent
        
        if self.progress_percentage >= 100.0:
            self.complete_material()
        elif self.status == MaterialProgressStatus.NOT_STARTED:
            self.start_material()


class UserModuleProgress(Base):
    """Track user progress for course modules"""
    __tablename__ = "user_module_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    enrollment_id = Column(Integer, ForeignKey("enrollments.id"), nullable=False)
    module_id = Column(Integer, ForeignKey("course_modules.id"), nullable=False)
    status = Column(String(20), default=MaterialProgressStatus.NOT_STARTED, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    progress_percentage = Column(Float, default=0.0)
    materials_completed = Column(Integer, default=0)
    total_materials = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User")
    enrollment = relationship("Enrollment")
    module = relationship("CourseModule")

    def __repr__(self):
        return f"<UserModuleProgress(id={self.id}, user_id={self.user_id}, module_id={self.module_id}, status={self.status})>"

    def calculate_progress(self):
        """Calculate module progress based on completed materials"""
        if self.total_materials > 0:
            self.progress_percentage = (self.materials_completed / self.total_materials) * 100
            if self.progress_percentage >= 100.0:
                self.status = MaterialProgressStatus.COMPLETED
                if not self.completed_at:
                    self.completed_at = datetime.utcnow()
            elif self.progress_percentage > 0:
                self.status = MaterialProgressStatus.IN_PROGRESS
                if not self.started_at:
                    self.started_at = datetime.utcnow()