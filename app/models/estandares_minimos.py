from sqlalchemy import (
    Column, Integer, String, Text, Float,
    DateTime, ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base


class GrupoEstandar(str, enum.Enum):
    GRUPO_7  = "GRUPO_7"    # <10 trabajadores, Riesgo I/II/III
    GRUPO_21 = "GRUPO_21"   # 11-50 trabajadores, Riesgo I/II/III
    GRUPO_60 = "GRUPO_60"   # >50 trabajadores o Riesgo IV/V


class NivelRiesgoEmpresa(str, enum.Enum):
    NIVEL_I   = "I"
    NIVEL_II  = "II"
    NIVEL_III = "III"
    NIVEL_IV  = "IV"
    NIVEL_V   = "V"


class EstadoAutoevaluacion(str, enum.Enum):
    BORRADOR   = "borrador"
    EN_PROCESO = "en_proceso"
    FINALIZADA = "finalizada"


class NivelCumplimiento(str, enum.Enum):
    CRITICO                 = "critico"                   # < 60%
    MODERADAMENTE_ACEPTABLE = "moderadamente_aceptable"   # 60-85%
    ACEPTABLE               = "aceptable"                 # > 85%


class CicloPHVA(str, enum.Enum):
    PLANEAR   = "PLANEAR"
    HACER     = "HACER"
    VERIFICAR = "VERIFICAR"
    ACTUAR    = "ACTUAR"


class ValorCumplimiento(str, enum.Enum):
    CUMPLE_TOTALMENTE = "cumple_totalmente"  # puntos completos
    NO_CUMPLE         = "no_cumple"          # 0 puntos
    NO_APLICA         = "no_aplica"          # puntos completos, requiere justificación


class AutoevaluacionEstandares(Base):
    __tablename__ = "autoevaluacion_estandares"

    id               = Column(Integer, primary_key=True, index=True)
    año              = Column(Integer, nullable=False)
    empresa_id       = Column(Integer, ForeignKey("empresas.id"), nullable=True)
    num_trabajadores = Column(Integer, nullable=False)
    nivel_riesgo     = Column(SAEnum(NivelRiesgoEmpresa, name="nivel_riesgo_empresa_enum", create_type=True, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    grupo            = Column(SAEnum(GrupoEstandar, name="grupo_estandar_enum", create_type=True, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    estado           = Column(SAEnum(EstadoAutoevaluacion, name="estado_autoevaluacion_enum", create_type=True, values_callable=lambda obj: [e.value for e in obj]), default=EstadoAutoevaluacion.BORRADOR)
    # Scores cacheados (actualizados tras cada respuesta)
    puntaje_total     = Column(Float, default=0.0)
    puntaje_planear   = Column(Float, default=0.0)
    puntaje_hacer     = Column(Float, default=0.0)
    puntaje_verificar = Column(Float, default=0.0)
    puntaje_actuar    = Column(Float, default=0.0)
    nivel_cumplimiento = Column(SAEnum(NivelCumplimiento, name="nivel_cumplimiento_enum", create_type=True, values_callable=lambda obj: [e.value for e in obj]), nullable=True)
    # Metadata
    encargado_sgsst         = Column(String(200), nullable=True)
    observaciones_generales = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    respuestas = relationship(
        "AutoevaluacionRespuesta",
        back_populates="autoevaluacion",
        cascade="all, delete-orphan",
        order_by="AutoevaluacionRespuesta.orden"
    )


class AutoevaluacionRespuesta(Base):
    __tablename__ = "autoevaluacion_respuesta"

    id                    = Column(Integer, primary_key=True, index=True)
    autoevaluacion_id     = Column(Integer, ForeignKey("autoevaluacion_estandares.id"), nullable=False)
    estandar_codigo       = Column(String(20), nullable=False)      # ej. "1.1.1"
    ciclo                 = Column(SAEnum(CicloPHVA, name="ciclo_phva_estandares_enum", create_type=True, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    descripcion           = Column(Text, nullable=False)
    valor_maximo          = Column(Float, nullable=False)            # peso original (60-grupo)
    valor_maximo_ajustado = Column(Float, nullable=False)            # peso normalizado a 100
    cumplimiento          = Column(SAEnum(ValorCumplimiento, name="valor_cumplimiento_enum", create_type=True, values_callable=lambda obj: [e.value for e in obj]), default=ValorCumplimiento.NO_CUMPLE)
    valor_obtenido        = Column(Float, default=0.0)
    justificacion_no_aplica = Column(Text, nullable=True)           # requerida cuando NO_APLICA
    observaciones         = Column(Text, nullable=True)
    orden                 = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    autoevaluacion = relationship("AutoevaluacionEstandares", back_populates="respuestas")
