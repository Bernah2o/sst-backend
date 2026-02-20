from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Float,
    DateTime, Date, ForeignKey
)
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class ProgramaCapacitaciones(Base):
    __tablename__ = "programa_capacitaciones"

    id = Column(Integer, primary_key=True, index=True)
    año = Column(Integer, nullable=False)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=True)
    codigo = Column(String(50), default="PR-SST-01")
    version = Column(String(20), default="1")
    titulo = Column(String(300), default="PROGRAMA DE CAPACITACIONES")
    alcance = Column(Text, default="Aplica para todos los trabajadores de la organización")
    objetivo = Column(Text, default="Prevenir la ocurrencia de accidentes y enfermedades laborales asociados a las actividades de la compañía por medio de capacitaciones")
    recursos = Column(Text, default="Económicos, Técnicos, Humanos, Infraestructura")
    meta_cumplimiento = Column(Float, default=90.0)
    meta_cobertura = Column(Float, default=80.0)
    meta_eficacia = Column(Float, default=90.0)
    encargado_sgsst = Column(String(200), nullable=True)
    aprobado_por = Column(String(200), nullable=True)
    estado = Column(String(30), default="borrador")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    actividades = relationship(
        "CapacitacionActividad",
        back_populates="programa",
        cascade="all, delete-orphan",
        order_by="CapacitacionActividad.orden"
    )
    indicadores_mensuales = relationship(
        "CapacitacionIndicadorMensual",
        back_populates="programa",
        cascade="all, delete-orphan",
        order_by="CapacitacionIndicadorMensual.mes"
    )


class CapacitacionActividad(Base):
    __tablename__ = "capacitacion_actividad"

    id = Column(Integer, primary_key=True, index=True)
    programa_id = Column(Integer, ForeignKey("programa_capacitaciones.id", ondelete="CASCADE"), nullable=False)
    ciclo = Column(String(30), nullable=False)  # I_PLANEAR | II_HACER | III_VERIFICAR | IV_ACTUAR
    nombre = Column(Text, nullable=False)
    encargado = Column(String(300), nullable=True)
    recursos = Column(String(300), nullable=True)
    horas = Column(Float, nullable=True, default=0)
    orden = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    programa = relationship("ProgramaCapacitaciones", back_populates="actividades")
    seguimientos = relationship(
        "CapacitacionSeguimiento",
        back_populates="actividad",
        cascade="all, delete-orphan",
        order_by="CapacitacionSeguimiento.mes"
    )


class CapacitacionSeguimiento(Base):
    __tablename__ = "capacitacion_seguimiento"

    id = Column(Integer, primary_key=True, index=True)
    actividad_id = Column(Integer, ForeignKey("capacitacion_actividad.id", ondelete="CASCADE"), nullable=False)
    mes = Column(Integer, nullable=False)       # 1-12
    programada = Column(Boolean, default=False) # P
    ejecutada = Column(Boolean, default=False)  # E
    observacion = Column(Text, nullable=True)
    fecha_ejecucion = Column(Date, nullable=True)
    ejecutado_por = Column(String(200), nullable=True)
    trabajadores_programados = Column(Integer, default=0)
    trabajadores_participaron = Column(Integer, default=0)
    personas_evaluadas = Column(Integer, default=0)
    evaluaciones_eficaces = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    actividad = relationship("CapacitacionActividad", back_populates="seguimientos")


class CapacitacionIndicadorMensual(Base):
    """
    Almacena los valores mensuales de los 3 indicadores (fichas técnicas del PDF).
    Se crean 36 filas al crear desde plantilla: 3 indicadores × 12 meses.
    El análisis trimestral se guarda en mes = 3, 6, 9, 12.
    """
    __tablename__ = "capacitacion_indicador_mensual"

    id = Column(Integer, primary_key=True, index=True)
    programa_id = Column(Integer, ForeignKey("programa_capacitaciones.id", ondelete="CASCADE"), nullable=False)
    tipo_indicador = Column(String(20), nullable=False)  # CUMPLIMIENTO | COBERTURA | EFICACIA
    mes = Column(Integer, nullable=False)                # 1-12
    numerador = Column(Float, default=0)
    denominador = Column(Float, default=0)
    valor_porcentaje = Column(Float, default=0)
    meta = Column(Float, nullable=True)
    analisis_trimestral = Column(Text, nullable=True)    # solo meses 3, 6, 9, 12
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    programa = relationship("ProgramaCapacitaciones", back_populates="indicadores_mensuales")
