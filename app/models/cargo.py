from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Cargo(Base):
    """Modelo para cargos/posiciones de trabajo"""
    __tablename__ = "cargos"

    id = Column(Integer, primary_key=True, index=True)
    nombre_cargo = Column(String(100), nullable=False, unique=True, index=True)
    periodicidad_emo = Column(String(50), nullable=True)  # Periodicidad de exámenes médicos ocupacionales
    activo = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    profesiogramas = relationship("Profesiograma", back_populates="cargo", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Cargo(id={self.id}, nombre_cargo='{self.nombre_cargo}', activo={self.activo})>"
