from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, Date, ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base


class EstadoPrograma(str, enum.Enum):
    BORRADOR = "borrador"
    ACTIVO = "activo"
    FINALIZADO = "finalizado"


class CicloInspeccion(str, enum.Enum):
    PLANEAR = "planear"
    HACER = "hacer"
    VERIFICAR = "verificar"
    ACTUAR = "actuar"


class TipoInspeccion(str, enum.Enum):
    LOCATIVA = "locativa"
    EQUIPOS = "equipos"
    HERRAMIENTAS = "herramientas"
    EPP = "epp"
    EXTINTORES = "extintores"
    PRIMEROS_AUXILIOS = "primeros_auxilios"
    ORDEN_ASEO = "orden_aseo"
    ELECTRICA = "electrica"
    EMERGENCIAS = "emergencias"
    QUIMICOS = "quimicos"
    VEHICULOS = "vehiculos"
    BOTIQUIN = "botiquin"
    GENERAL = "general"


class FrecuenciaInspeccion(str, enum.Enum):
    MENSUAL = "mensual"
    BIMESTRAL = "bimestral"
    TRIMESTRAL = "trimestral"
    SEMESTRAL = "semestral"
    ANUAL = "anual"


class ProgramaInspecciones(Base):
    __tablename__ = "programa_inspecciones"

    id = Column(Integer, primary_key=True, index=True)
    año = Column(Integer, nullable=False)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=True)
    codigo = Column(String(50), default="PR-SST-02")
    version = Column(String(20), default="1")
    objetivo = Column(
        Text,
        default="Prevenir la ocurrencia de accidentes y enfermedades laborales asociadas a las actividades de la compañía por medio de las inspecciones."
    )
    alcance = Column(
        Text,
        default="Este programa aplica para todas las áreas de trabajo de la empresa."
    )
    recursos = Column(
        String(500),
        default="Económicos, Técnicos, Humanos, Infraestructura"
    )
    legislacion_aplicable = Column(Text, nullable=True)
    encargado_sgsst = Column(String(200), nullable=True)
    aprobado_por = Column(String(200), nullable=True)
    estado = Column(
        SAEnum(EstadoPrograma, name="estadoprogramainspeccion", values_callable=lambda obj: [e.value for e in obj]),
        default=EstadoPrograma.BORRADOR
    )
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    inspecciones = relationship(
        "InspeccionProgramada",
        back_populates="programa",
        cascade="all, delete-orphan",
        order_by="InspeccionProgramada.orden"
    )


class InspeccionProgramada(Base):
    __tablename__ = "inspeccion_programada"

    id = Column(Integer, primary_key=True, index=True)
    programa_id = Column(Integer, ForeignKey("programa_inspecciones.id"), nullable=False)
    ciclo = Column(
        SAEnum(CicloInspeccion, name="cicloinspeccion", values_callable=lambda obj: [e.value for e in obj]),
        default=CicloInspeccion.HACER,
        nullable=False
    )
    tipo_inspeccion = Column(
        SAEnum(TipoInspeccion, name="tipoinspeccion", values_callable=lambda obj: [e.value for e in obj]),
        nullable=False
    )
    area = Column(String(200), nullable=False)
    descripcion = Column(Text, nullable=False)
    responsable = Column(String(300), nullable=True)
    frecuencia = Column(
        SAEnum(FrecuenciaInspeccion, name="frecuenciainspeccion", values_callable=lambda obj: [e.value for e in obj]),
        default=FrecuenciaInspeccion.MENSUAL
    )
    lista_chequeo = Column(String(300), nullable=True)
    observaciones = Column(Text, nullable=True)
    orden = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    programa = relationship("ProgramaInspecciones", back_populates="inspecciones")
    seguimientos = relationship(
        "InspeccionSeguimiento",
        back_populates="inspeccion",
        cascade="all, delete-orphan",
        order_by="InspeccionSeguimiento.mes"
    )


class InspeccionSeguimiento(Base):
    __tablename__ = "inspeccion_seguimiento"

    id = Column(Integer, primary_key=True, index=True)
    inspeccion_id = Column(Integer, ForeignKey("inspeccion_programada.id"), nullable=False)
    mes = Column(Integer, nullable=False)  # 1-12
    programada = Column(Boolean, default=False)
    ejecutada = Column(Boolean, default=False)
    condiciones_peligrosas_reportadas = Column(Integer, default=0)
    condiciones_peligrosas_intervenidas = Column(Integer, default=0)
    fecha_ejecucion = Column(Date, nullable=True)
    ejecutado_por = Column(String(200), nullable=True)
    hallazgos = Column(Text, nullable=True)
    accion_correctiva = Column(Text, nullable=True)
    observacion = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    inspeccion = relationship("InspeccionProgramada", back_populates="seguimientos")
