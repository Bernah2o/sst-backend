from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class ProgramaSVE(Base):
    __tablename__ = "programas_sve"

    id = Column(Integer, primary_key=True, index=True)
    profesiograma_id = Column(Integer, ForeignKey("profesiogramas.id"), nullable=False, index=True)
    nombre = Column(String(200), nullable=False)
    descripcion = Column(Text)

    profesiograma = relationship("Profesiograma", back_populates="programas_sve")

    def __repr__(self):
        return f"<ProgramaSVE(id={self.id}, nombre='{self.nombre}', profesiograma_id={self.profesiograma_id})>"

