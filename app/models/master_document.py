from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class MasterDocument(Base):
    __tablename__ = "master_documents"
    __table_args__ = (
        UniqueConstraint("empresa_id", "codigo", name="uq_master_documents_empresa_codigo"),
        Index("ix_master_documents_codigo", "codigo"),
        Index("ix_master_documents_tipo_documento", "tipo_documento"),
        Index("ix_master_documents_empresa_id", "empresa_id"),
    )

    id = Column(Integer, primary_key=True, index=True)

    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=True)

    tipo_documento = Column(String(120), nullable=False)
    nombre_documento = Column(String(300), nullable=False)
    version = Column(String(20), nullable=True)
    codigo = Column(String(50), nullable=False)
    fecha = Column(Date, nullable=True)
    fecha_texto = Column(String(20), nullable=True)
    ubicacion = Column(String(500), nullable=True)
    support_file_key = Column(String(500), nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)

    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    empresa = relationship("Empresa")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])

    def __repr__(self):
        return f"<MasterDocument(id={self.id}, codigo='{self.codigo}', nombre='{self.nombre_documento}')>"

