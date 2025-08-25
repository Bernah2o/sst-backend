from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Enum as SQLEnum, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class UserRole(str, Enum):
    ADMIN = "admin"
    TRAINER = "trainer"
    EMPLOYEE = "employee"
    SUPERVISOR = "supervisor"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    document_type = Column(String(20), nullable=False)  # CC, CE, TI, etc.
    document_number = Column(String(50), unique=True, nullable=False)
    phone = Column(String(20))
    department = Column(String(100))
    position = Column(String(100))
    hire_date = Column(DateTime)
    role = Column(SQLEnum(UserRole), default=UserRole.EMPLOYEE, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    profile_picture = Column(String(255))
    emergency_contact_name = Column(String(100))
    emergency_contact_phone = Column(String(20))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)
    password_reset_token = Column(String(255))
    password_reset_expires = Column(DateTime)
    email_verification_token = Column(String(255))
    email_verification_expires = Column(DateTime)

    # Relationships
    user_evaluations = relationship("UserEvaluation", back_populates="user")
    user_surveys = relationship("UserSurvey", back_populates="user")
    certificates = relationship("Certificate", foreign_keys="Certificate.user_id", back_populates="user")
    attendances = relationship("Attendance", foreign_keys="Attendance.user_id", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")
    enrollments = relationship("Enrollment", back_populates="user")
    
    # Progress relationships
    material_progress = relationship("UserMaterialProgress", back_populates="user")
    module_progress = relationship("UserModuleProgress", back_populates="user")
    
    # Creator relationships
    created_courses = relationship("Course", foreign_keys="Course.created_by")
    created_evaluations = relationship("Evaluation", foreign_keys="Evaluation.created_by")
    created_surveys = relationship("Survey", foreign_keys="Survey.created_by")

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    def is_trainer(self) -> bool:
        return self.role == UserRole.TRAINER

    def is_employee(self) -> bool:
        return self.role == UserRole.EMPLOYEE

    def is_supervisor(self) -> bool:
        return self.role == UserRole.SUPERVISOR

    def can_manage_users(self) -> bool:
        return self.role in [UserRole.ADMIN, UserRole.SUPERVISOR]

    def can_create_courses(self) -> bool:
        return self.role in [UserRole.ADMIN, UserRole.TRAINER]

    def can_view_reports(self) -> bool:
        return self.role in [UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.TRAINER]