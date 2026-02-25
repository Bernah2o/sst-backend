from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Float,
    DateTime, Date, Numeric, ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base


class EstadoPlan(str, enum.Enum):
    BORRADOR = "borrador"
    APROBADO = "aprobado"
    EN_EJECUCION = "en_ejecucion"
    FINALIZADO = "finalizado"


class CicloPhva(str, enum.Enum):
    I_PLANEAR = "I_PLANEAR"
    II_HACER = "II_HACER"
    III_VERIFICAR = "III_VERIFICAR"
    IV_ACTUAR = "IV_ACTUAR"


class CategoriaActividad(str, enum.Enum):
    RECURSOS = "RECURSOS"
    GESTION_INTEGRAL = "GESTION_INTEGRAL"
    GESTION_SALUD = "GESTION_SALUD"
    GESTION_PELIGROS = "GESTION_PELIGROS"
    GESTION_AMENAZAS = "GESTION_AMENAZAS"
    VERIFICACION = "VERIFICACION"
    MEJORAMIENTO = "MEJORAMIENTO"


class PlanTrabajoAnual(Base):
    __tablename__ = "plan_trabajo_anual"

    id = Column(Integer, primary_key=True, index=True)
    año = Column(Integer, nullable=False)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=True)
    codigo = Column(String(50), default="PL-SST-02")
    version = Column(String(20), default="1")
    objetivo = Column(Text, default="Planear y controlar la ejecución de actividades de seguridad y salud en el trabajo")
    alcance = Column(Text, default="Aplica para los empleados, contratistas y subcontratistas de la Empresa")
    meta = Column(String(500), default="Garantizar el cumplimiento del 95% de las actividades programadas en el Plan de Trabajo anual")
    meta_porcentaje = Column(Float, default=90.0)
    indicador = Column(String(500), default="(Numero de actividades ejecutadas / numero de actividades programadas) * 100")
    formula = Column(String(500), default="N° de Actividades Programadas / N° de Actividades Ejecutadas")
    encargado_sgsst = Column(String(200), nullable=True)
    aprobado_por = Column(String(200), nullable=True)
    estado = Column(
        SAEnum(EstadoPlan, name="estadoplan", values_callable=lambda obj: [e.value for e in obj]), 
        default=EstadoPlan.BORRADOR
    )
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    actividades = relationship(
        "PlanTrabajoActividad",
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="PlanTrabajoActividad.orden"
    )


class PlanTrabajoActividad(Base):
    __tablename__ = "plan_trabajo_actividad"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("plan_trabajo_anual.id"), nullable=False)
    ciclo = Column(
        SAEnum(CicloPhva, name="ciclophva", values_callable=lambda obj: [e.value for e in obj]), 
        nullable=False
    )
    categoria = Column(
        SAEnum(CategoriaActividad, name="categoriaactividad", values_callable=lambda obj: [e.value for e in obj]), 
        nullable=False
    )
    estandar = Column(String(200), nullable=True)
    descripcion = Column(Text, nullable=False)
    frecuencia = Column(String(100), nullable=True)
    responsable = Column(String(300), nullable=True)
    recurso_financiero = Column(Boolean, default=False)
    recurso_tecnico = Column(Boolean, default=False)
    costo = Column(Numeric(12, 2), nullable=True)
    observaciones = Column(Text, nullable=True)
    orden = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    plan = relationship("PlanTrabajoAnual", back_populates="actividades")
    seguimientos_mensuales = relationship(
        "PlanTrabajoSeguimiento",
        back_populates="actividad",
        cascade="all, delete-orphan",
        order_by="PlanTrabajoSeguimiento.mes"
    )


class PlanTrabajoSeguimiento(Base):
    __tablename__ = "plan_trabajo_seguimiento"

    id = Column(Integer, primary_key=True, index=True)
    actividad_id = Column(Integer, ForeignKey("plan_trabajo_actividad.id"), nullable=False)
    mes = Column(Integer, nullable=False)  # 1-12
    programada = Column(Boolean, default=False)
    ejecutada = Column(Boolean, default=False)
    observacion = Column(Text, nullable=True)
    fecha_ejecucion = Column(Date, nullable=True)
    ejecutado_por = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    actividad = relationship("PlanTrabajoActividad", back_populates="seguimientos_mensuales")
