"""
Modelo de Sector Económico para la Matriz Legal SST.
Catálogo de sectores económicos para filtrado de normas aplicables.
"""

from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class SectorEconomico(Base):
    """
    Catálogo de sectores económicos para filtrado de normas.
    Incluye un sector especial "TODOS LOS SECTORES" para normas generales.
    """
    __tablename__ = "sectores_economicos"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(20), nullable=True, unique=True, index=True)
    nombre = Column(String(200), nullable=False, unique=True, index=True)
    descripcion = Column(Text, nullable=True)

    # Para manejar "TODOS LOS SECTORES" como valor especial
    es_todos_los_sectores = Column(Boolean, default=False, nullable=False)

    activo = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    empresas = relationship("Empresa", back_populates="sector_economico")
    normas = relationship("MatrizLegalNorma", back_populates="sector_economico")

    def __repr__(self):
        return f"<SectorEconomico(id={self.id}, nombre='{self.nombre}')>"
