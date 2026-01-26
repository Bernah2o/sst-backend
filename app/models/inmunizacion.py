
from sqlalchemy import Column, Integer, String, Boolean, Text
from app.database import Base

class Inmunizacion(Base):
    __tablename__ = "inmunizaciones"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), unique=True, nullable=False, index=True)
    descripcion = Column(Text, nullable=True)
    activo = Column(Boolean, default=True)

    def __repr__(self):
        return f"<Inmunizacion(id={self.id}, nombre='{self.nombre}', activo={self.activo})>"
