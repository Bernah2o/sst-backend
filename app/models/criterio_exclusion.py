from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class CriterioExclusion(Base):
    __tablename__ = "criterios_exclusion"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(200), unique=True, index=True, nullable=False)
    descripcion = Column(Text)

    profesiogramas = relationship(
        "Profesiograma",
        secondary="profesiograma_criterio_exclusion",
        back_populates="criterios_exclusion",
    )

    def __repr__(self):
        return f"<CriterioExclusion(id={self.id}, nombre='{self.nombre}')>"

