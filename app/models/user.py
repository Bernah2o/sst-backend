from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text
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
    custom_role_id = Column(Integer, ForeignKey("custom_roles.id"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    profile_picture = Column(String(255))
    emergency_contact_name = Column(String(100))
    emergency_contact_phone = Column(String(20))
    notes = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime)
    password_reset_token = Column(String(255))
    password_reset_expires = Column(DateTime)
    email_verification_token = Column(String(255))
    email_verification_expires = Column(DateTime)
    
    # Campos para control de intentos fallidos de login
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    account_locked_until = Column(DateTime, nullable=True)
    last_failed_login = Column(DateTime, nullable=True)

    # Relationships
    custom_role = relationship("CustomRole", back_populates="users")
    user_evaluations = relationship("UserEvaluation", back_populates="user")
    user_surveys = relationship("UserSurvey", back_populates="user")
    certificates = relationship("Certificate", foreign_keys="Certificate.user_id", back_populates="user")
    attendances = relationship("Attendance", foreign_keys="Attendance.user_id", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")
    enrollments = relationship("Enrollment", back_populates="user")
    created_virtual_sessions = relationship("VirtualSession", back_populates="creator")
    
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
    
    def is_account_locked(self) -> bool:
        """Verifica si la cuenta está bloqueada por intentos fallidos"""
        # La cuenta está bloqueada si tiene 3 o más intentos fallidos
        # Solo se puede desbloquear mediante restablecimiento de contraseña
        return self.failed_login_attempts >= 3
    
    def increment_failed_login_attempts(self) -> None:
        """Incrementa el contador de intentos fallidos"""
        self.failed_login_attempts += 1
        self.last_failed_login = datetime.now(timezone.utc)
    
    def reset_failed_login_attempts(self) -> None:
        """Resetea el contador de intentos fallidos después de un login exitoso o restablecimiento de contraseña"""
        self.failed_login_attempts = 0
        self.account_locked_until = None
        self.last_failed_login = None
    
    def generate_password_reset_token(self) -> str:
        """Genera un token para restablecimiento de contraseña"""
        import secrets
        token = secrets.token_urlsafe(32)
        self.password_reset_token = token
        self.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)  # Token válido por 1 hora
        return token
    
    def verify_password_reset_token(self, token: str) -> bool:
        """Verifica si el token de restablecimiento es válido"""
        if not self.password_reset_token or not self.password_reset_expires:
            return False
        
        if datetime.now(timezone.utc) > self.password_reset_expires:
            return False
            
        return self.password_reset_token == token
    
    def clear_password_reset_token(self) -> None:
        """Limpia el token de restablecimiento después de usarlo"""
        self.password_reset_token = None
        self.password_reset_expires = None