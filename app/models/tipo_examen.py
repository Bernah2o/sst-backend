from sqlalchemy import Boolean, Column, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class TipoExamen(Base):
    __tablename__ = "tipos_examen"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(150), unique=True, index=True, nullable=False)
    descripcion = Column(Text)
    activo = Column(Boolean, default=True, nullable=False)

    profesiogramas = relationship(
        "Profesiograma",
        secondary="profesiograma_examenes",
        back_populates="tipos_examen",
        overlaps="examenes,profesiograma",
    )
    profesiograma_examenes = relationship(
        "ProfesiogramaExamen",
        back_populates="tipo_examen",
        cascade="all, delete-orphan",
        overlaps="profesiogramas,tipos_examen",
    )

    def __repr__(self):
        return f"<TipoExamen(id={self.id}, nombre='{self.nombre}', activo={self.activo})>"
