from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    Date,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class CronogramaPyp(Base):
    __tablename__ = "cronograma_pyp"

    id = Column(Integer, primary_key=True, index=True)
    plan_trabajo_anual_id = Column(
        Integer, ForeignKey("plan_trabajo_anual.id"), nullable=False, unique=True
    )

    año = Column(Integer, nullable=False)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=True)

    codigo = Column(String(50), default="CR-PYP-01")
    version = Column(String(20), default="1")
    objetivo = Column(
        Text,
        default=(
            "Planificar y controlar la ejecución de actividades del Programa de Promoción y Prevención (PYP)"
        ),
    )
    alcance = Column(
        Text,
        default=(
            "Aplica para los trabajadores, contratistas y subcontratistas de la Empresa"
        ),
    )
    encargado_sgsst = Column(String(200), nullable=True)
    aprobado_por = Column(String(200), nullable=True)

    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    actividades = relationship(
        "CronogramaPypActividad",
        back_populates="cronograma",
        cascade="all, delete-orphan",
        order_by="CronogramaPypActividad.orden",
    )


class CronogramaPypActividad(Base):
    __tablename__ = "cronograma_pyp_actividad"

    id = Column(Integer, primary_key=True, index=True)
    cronograma_id = Column(
        Integer, ForeignKey("cronograma_pyp.id"), nullable=False
    )

    actividad = Column(Text, nullable=False)
    poblacion_objetivo = Column(String(500), nullable=True)
    responsable = Column(String(300), nullable=True)
    indicador = Column(String(500), nullable=True)
    recursos = Column(String(500), nullable=True)
    observaciones = Column(Text, nullable=True)
    orden = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cronograma = relationship("CronogramaPyp", back_populates="actividades")
    seguimientos_mensuales = relationship(
        "CronogramaPypSeguimiento",
        back_populates="actividad_ref",
        cascade="all, delete-orphan",
        order_by="CronogramaPypSeguimiento.mes",
    )


class CronogramaPypSeguimiento(Base):
    __tablename__ = "cronograma_pyp_seguimiento"

    id = Column(Integer, primary_key=True, index=True)
    actividad_id = Column(
        Integer, ForeignKey("cronograma_pyp_actividad.id"), nullable=False
    )
    mes = Column(Integer, nullable=False)
    programada = Column(Boolean, default=False)
    ejecutada = Column(Boolean, default=False)
    observacion = Column(Text, nullable=True)
    fecha_ejecucion = Column(Date, nullable=True)
    ejecutado_por = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    actividad_ref = relationship("CronogramaPypActividad", back_populates="seguimientos_mensuales")

