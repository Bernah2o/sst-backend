from datetime import datetime, date, timedelta
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Date,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class ReinductionStatus(str, Enum):
    PENDING = "pending"  # Reinducción requerida pero no programada
    SCHEDULED = "scheduled"  # Reinducción programada
    IN_PROGRESS = "in_progress"  # Trabajador inscrito en curso
    COMPLETED = "completed"  # Reinducción completada
    OVERDUE = "overdue"  # Reinducción vencida
    EXEMPTED = "exempted"  # Exento de reinducción


class ReinductionRecord(Base):
    """Modelo para rastrear las reinducciones requeridas y completadas por cada trabajador"""
    __tablename__ = "reinduction_records"

    id = Column(Integer, primary_key=True, index=True)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False)
    year = Column(Integer, nullable=False)  # Año de la reinducción requerida
    due_date = Column(Date, nullable=False)  # Fecha límite para completar la reinducción
    status = Column(SQLEnum(ReinductionStatus), default=ReinductionStatus.PENDING, nullable=False)
    
    # Información del curso asignado
    assigned_course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    enrollment_id = Column(Integer, ForeignKey("enrollments.id"), nullable=True)
    
    # Fechas importantes
    scheduled_date = Column(Date, nullable=True)  # Fecha programada para la reinducción
    completed_date = Column(Date, nullable=True)  # Fecha de finalización
    
    # Notificaciones
    first_notification_sent = Column(DateTime, nullable=True)
    reminder_notification_sent = Column(DateTime, nullable=True)
    overdue_notification_sent = Column(DateTime, nullable=True)
    
    # Observaciones
    notes = Column(Text, nullable=True)
    exemption_reason = Column(Text, nullable=True)  # Razón de exención si aplica
    
    # Metadatos
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # Admin que creó el registro
    
    # Relationships
    worker = relationship("Worker", back_populates="reinduction_records")
    assigned_course = relationship("Course", foreign_keys=[assigned_course_id])
    enrollment = relationship("Enrollment", foreign_keys=[enrollment_id])
    creator = relationship("User", foreign_keys=[created_by])
    
    def __repr__(self):
        return f"<ReinductionRecord(id={self.id}, worker_id={self.worker_id}, year={self.year}, status={self.status})>"
    
    @property
    def is_overdue(self) -> bool:
        """Verifica si la reinducción está vencida"""
        if self.status == ReinductionStatus.COMPLETED:
            return False
        return date.today() > self.due_date
    
    @property
    def days_until_due(self) -> int:
        """Días restantes hasta la fecha límite"""
        return (self.due_date - date.today()).days
    
    @property
    def needs_notification(self) -> bool:
        """Determina si necesita notificación basado en días restantes"""
        days_left = self.days_until_due
        
        # Primera notificación: 60 días antes
        if days_left <= 60 and not self.first_notification_sent:
            return True
        
        # Recordatorio: 30 días antes
        if days_left <= 30 and not self.reminder_notification_sent:
            return True
        
        # Notificación de vencimiento: después de la fecha límite
        if days_left < 0 and not self.overdue_notification_sent:
            return True
        
        return False


class ReinductionConfig(Base):
    """Configuración global para el sistema de reinducciones"""
    __tablename__ = "reinduction_config"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Configuración de notificaciones (días antes de la fecha límite)
    first_notification_days = Column(Integer, default=60, nullable=False)
    reminder_notification_days = Column(Integer, default=30, nullable=False)
    
    # Configuración de fechas
    grace_period_days = Column(Integer, default=30, nullable=False)  # Días de gracia después del aniversario
    
    # Configuración de cursos
    default_reinduction_course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    auto_enroll_enabled = Column(Boolean, default=False, nullable=False)  # Auto-inscripción automática
    
    # Configuración de automatización
    auto_check_enabled = Column(Boolean, default=True, nullable=False)  # Verificación automática diaria
    auto_notification_enabled = Column(Boolean, default=True, nullable=False)  # Notificaciones automáticas
    
    # Metadatos
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    default_course = relationship("Course", foreign_keys=[default_reinduction_course_id])
    updater = relationship("User", foreign_keys=[updated_by])
    
    def __repr__(self):
        return f"<ReinductionConfig(id={self.id}, auto_check={self.auto_check_enabled})>"