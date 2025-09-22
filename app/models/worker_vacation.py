from datetime import datetime, date
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Date, Enum as SQLEnum, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property

from app.database import Base


class VacationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class WorkerVacation(Base):
    __tablename__ = "worker_vacations"

    id = Column(Integer, primary_key=True, index=True)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False, index=True)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=False, index=True)
    days = Column(Integer, nullable=False)  # Días laborales solicitados
    reason = Column(Text, nullable=False)
    status = Column(SQLEnum(VacationStatus), default=VacationStatus.PENDING, nullable=False, index=True)
    
    # Información de solicitud
    request_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    requested_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Información de aprobación/rechazo
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_date = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Metadatos
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relaciones
    worker = relationship("Worker", back_populates="vacations")
    requested_by_user = relationship("User", foreign_keys=[requested_by])
    approved_by_user = relationship("User", foreign_keys=[approved_by])

    @hybrid_property
    def is_approved(self) -> bool:
        return self.status == VacationStatus.APPROVED

    @hybrid_property
    def is_pending(self) -> bool:
        return self.status == VacationStatus.PENDING

    @hybrid_property
    def is_rejected(self) -> bool:
        return self.status == VacationStatus.REJECTED

    def __repr__(self):
        return f"<WorkerVacation(id={self.id}, worker_id={self.worker_id}, start_date={self.start_date}, end_date={self.end_date}, status={self.status})>"


class VacationBalance(Base):
    __tablename__ = "vacation_balances"

    id = Column(Integer, primary_key=True, index=True)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False, unique=True, index=True)
    year = Column(Integer, nullable=False, index=True)
    total_days = Column(Integer, default=15, nullable=False)  # Días totales por año
    used_days = Column(Integer, default=0, nullable=False)    # Días ya utilizados
    pending_days = Column(Integer, default=0, nullable=False) # Días en solicitudes pendientes
    
    # Metadatos
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relaciones
    worker = relationship("Worker", back_populates="vacation_balance")

    @hybrid_property
    def available_days(self) -> int:
        return self.total_days - self.used_days - self.pending_days

    def __repr__(self):
        return f"<VacationBalance(id={self.id}, worker_id={self.worker_id}, year={self.year}, available_days={self.available_days})>"