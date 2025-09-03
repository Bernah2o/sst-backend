from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from app.database import Base


class NotificationAcknowledgment(Base):
    """Modelo para registrar confirmaciones de recepción de notificaciones"""
    __tablename__ = "notification_acknowledgments"

    id = Column(Integer, primary_key=True, index=True)
    
    # Relación con el trabajador que confirma la notificación
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False)
    
    # Relación con el examen ocupacional
    occupational_exam_id = Column(Integer, ForeignKey("occupational_exams.id"), nullable=False)
    
    # Tipo de notificación confirmada
    notification_type = Column(String(50), nullable=False)  # 'first_notification', 'reminder', 'overdue'
    
    # IP desde donde se confirmó (para auditoría)
    ip_address = Column(String(45), nullable=True)
    
    # User agent del navegador (para auditoría)
    user_agent = Column(String(500), nullable=True)
    
    # Indica si la confirmación detiene futuras notificaciones
    stops_notifications = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    acknowledged_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relaciones
    worker = relationship("Worker", foreign_keys=[worker_id])
    occupational_exam = relationship("OccupationalExam", foreign_keys=[occupational_exam_id])
    
    def __repr__(self):
        return f"<NotificationAcknowledgment(id={self.id}, worker_id={self.worker_id}, exam_id={self.occupational_exam_id}, type='{self.notification_type}')>"