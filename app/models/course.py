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


class CourseType(str, Enum):
    INDUCTION = "induction"
    REINDUCTION = "reinduction"
    SPECIALIZED = "specialized"
    MANDATORY = "mandatory"
    OPTIONAL = "optional"
    TRAINING = "training"


class CourseStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class MaterialType(str, Enum):
    PDF = "pdf"
    VIDEO = "video"
    LINK = "link"


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    course_type = Column(SQLEnum(CourseType), nullable=False)
    status = Column(SQLEnum(CourseStatus), default=CourseStatus.DRAFT)
    duration_hours = Column(Float)  # Duration in hours
    passing_score = Column(Float, default=70.0)  # Minimum score to pass
    max_attempts = Column(Integer, default=3)
    is_mandatory = Column(Boolean, default=False)
    thumbnail = Column(String(255))
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at = Column(DateTime)
    expires_at = Column(DateTime)  # Course expiration date
    order_index = Column(Integer, default=0)  # For ordering courses

    # Relationships
    creator = relationship(
        "User", foreign_keys=[created_by], overlaps="created_courses"
    )
    modules = relationship(
        "CourseModule", back_populates="course", cascade="all, delete-orphan"
    )
    enrollments = relationship("Enrollment", back_populates="course")
    # Note: Other relationships (evaluations, surveys, certificates, attendances)
    # are commented out because the corresponding tables don't have course_id columns
    evaluations = relationship(
        "Evaluation", back_populates="course", cascade="all, delete-orphan"
    )
    surveys = relationship("Survey", back_populates="course")
    certificates = relationship(
        "Certificate", back_populates="course", cascade="all, delete-orphan"
    )
    # attendances = relationship("Attendance", back_populates="course", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="course")

    def __repr__(self):
        return (
            f"<Course(id={self.id}, title='{self.title}', type='{self.course_type}')>"
        )


class CourseModule(Base):
    __tablename__ = "course_modules"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    order_index = Column(Integer, default=0)
    duration_minutes = Column(Integer)  # Duration in minutes
    is_required = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    course = relationship("Course", back_populates="modules")
    materials = relationship(
        "CourseMaterial", back_populates="module", cascade="all, delete-orphan"
    )
    module_progress = relationship("UserModuleProgress", back_populates="module")

    def __repr__(self):
        return f"<CourseModule(id={self.id}, title='{self.title}', course_id={self.course_id})>"


class CourseMaterial(Base):
    __tablename__ = "course_materials"

    id = Column(Integer, primary_key=True, index=True)
    module_id = Column(Integer, ForeignKey("course_modules.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    material_type = Column(SQLEnum(MaterialType), nullable=False)
    file_url = Column(String(500))  # External URL or uploaded file URL
    order_index = Column(Integer, default=0)
    is_downloadable = Column(Boolean, default=True)
    is_required = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    module = relationship("CourseModule", back_populates="materials")
    material_progress = relationship("UserMaterialProgress", back_populates="material")

    def __repr__(self):
        return f"<CourseMaterial(id={self.id}, title='{self.title}', type='{self.material_type}')>"