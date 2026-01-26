from enum import Enum

from sqlalchemy import Boolean, Column, Enum as SQLEnum, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class CategoriaFactorRiesgo(str, Enum):
    FISICO = "fisico"
    QUIMICO = "quimico"
    BIOLOGICO = "biologico"
    ERGONOMICO = "ergonomico"
    PSICOSOCIAL = "psicosocial"
    SEGURIDAD = "seguridad"


class FactorRiesgo(Base):
    __tablename__ = "factores_riesgo"

    id = Column(Integer, primary_key=True, index=True)

    codigo = Column(String(20), unique=True, index=True, nullable=False)
    nombre = Column(String(100), index=True, nullable=False)
    categoria = Column(
        SQLEnum(
            CategoriaFactorRiesgo,
            values_callable=lambda x: [e.value for e in x],
            name="categoriafactorriesgo",
        ),
        nullable=False,
    )

    descripcion = Column(Text)
    nivel_accion = Column(String(100))
    periodicidad_sugerida_meses = Column(Integer)
    normativa_aplicable = Column(String(200))
    examenes_sugeridos = Column(JSON)
    unidad_medida = Column(String(50))
    simbolo_unidad = Column(String(20))
    instrumento_medida = Column(String(80))
    requiere_sve = Column(Boolean, default=False, nullable=False)
    tipo_sve = Column(String(50))
    activo = Column(Boolean, default=True, nullable=False)

    profesiogramas = relationship(
        "Profesiograma",
        secondary="profesiograma_factores",
        back_populates="factores_riesgo",
        overlaps="profesiograma_factores,factor_riesgo,profesiograma",
        viewonly=True
    )

    def __repr__(self):
        return f"<FactorRiesgo(id={self.id}, codigo='{self.codigo}', nombre='{self.nombre}', categoria='{self.categoria}', activo={self.activo})>"
