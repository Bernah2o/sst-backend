from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SQLEnum

from app.database import Base


class DocumentCategory(str, Enum):
    IDENTIFICATION = "identificacion"
    CONTRACT = "contrato"
    MEDICAL = "medico"
    TRAINING = "capacitacion"
    CERTIFICATION = "certificacion"
    PERSONAL = "personal"
    OTROSI = "otrosi"
    OTHER = "otro"


class WorkerDocument(Base):
    __tablename__ = "worker_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False)
    
    # Información del documento
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(SQLEnum(DocumentCategory, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    
    # Información del archivo
    file_name = Column(String(255), nullable=False)
    file_url = Column(String(500), nullable=False)  # URL en Storage o local
    file_size = Column(Integer, nullable=True)  # Tamaño en bytes
    file_type = Column(String(100), nullable=True)  # MIME type
    
    # Metadatos
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    worker = relationship("Worker", back_populates="documents")
    uploader = relationship("User", foreign_keys=[uploaded_by])
    
    def __repr__(self):
        return f"<WorkerDocument(id={self.id}, worker_id={self.worker_id}, title='{self.title}')>"