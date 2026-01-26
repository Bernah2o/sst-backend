from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.orm import relationship

from app.database import Base


class ProfesiogramaInmunizacion(Base):
    __tablename__ = "profesiograma_inmunizaciones"

    id = Column(Integer, primary_key=True, index=True)
    profesiograma_id = Column(Integer, ForeignKey("profesiogramas.id"), nullable=False, index=True)
    inmunizacion_id = Column(Integer, ForeignKey("inmunizaciones.id"), nullable=False, index=True)

    profesiograma = relationship("Profesiograma", back_populates="inmunizaciones")
    inmunizacion = relationship("Inmunizacion")

    def __repr__(self):
        return (
            f"<ProfesiogramaInmunizacion(id={self.id}, inmunizacion_id={self.inmunizacion_id}, "
            f"profesiograma_id={self.profesiograma_id})>"
        )
