from pydantic import BaseModel, model_validator
from typing import Optional, List
from datetime import datetime

from app.models.estandares_minimos import (
    GrupoEstandar, NivelRiesgoEmpresa, EstadoAutoevaluacion,
    NivelCumplimiento, CicloPHVA, ValorCumplimiento
)


# ─────────────────────────────────────────────────────────────────────────────
# RESPUESTA INDIVIDUAL
# ─────────────────────────────────────────────────────────────────────────────

class AutoevaluacionRespuestaBase(BaseModel):
    estandar_codigo: str
    ciclo: CicloPHVA
    descripcion: str
    valor_maximo: float
    valor_maximo_ajustado: float
    cumplimiento: ValorCumplimiento = ValorCumplimiento.NO_CUMPLE
    justificacion_no_aplica: Optional[str] = None
    observaciones: Optional[str] = None
    orden: int = 0


class AutoevaluacionRespuestaUpdate(BaseModel):
    cumplimiento: ValorCumplimiento
    justificacion_no_aplica: Optional[str] = None
    observaciones: Optional[str] = None

    @model_validator(mode="after")
    def validar_justificacion_no_aplica(self):
        if self.cumplimiento == ValorCumplimiento.NO_APLICA:
            if not self.justificacion_no_aplica:
                raise ValueError(
                    "Se requiere 'justificacion_no_aplica' cuando el cumplimiento es NO_APLICA"
                )
        return self


class AutoevaluacionRespuestaResponse(AutoevaluacionRespuestaBase):
    id: int
    autoevaluacion_id: int
    valor_obtenido: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────────────────
# AUTOEVALUACIÓN (padre)
# ─────────────────────────────────────────────────────────────────────────────

class AutoevaluacionEstandaresBase(BaseModel):
    año: int
    empresa_id: Optional[int] = None
    num_trabajadores: int
    nivel_riesgo: NivelRiesgoEmpresa
    encargado_sgsst: Optional[str] = None
    observaciones_generales: Optional[str] = None


class AutoevaluacionEstandaresCreate(AutoevaluacionEstandaresBase):
    """El grupo se calcula en el servidor a partir de num_trabajadores + nivel_riesgo."""
    pass


class AutoevaluacionEstandaresUpdate(BaseModel):
    estado: Optional[EstadoAutoevaluacion] = None
    encargado_sgsst: Optional[str] = None
    observaciones_generales: Optional[str] = None


class AutoevaluacionEstandaresResponse(AutoevaluacionEstandaresBase):
    id: int
    grupo: GrupoEstandar
    estado: EstadoAutoevaluacion
    puntaje_total: float
    puntaje_planear: float
    puntaje_hacer: float
    puntaje_verificar: float
    puntaje_actuar: float
    nivel_cumplimiento: Optional[NivelCumplimiento] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AutoevaluacionEstandaresDetailResponse(AutoevaluacionEstandaresResponse):
    """Detalle completo con todas las respuestas hijo."""
    respuestas: List[AutoevaluacionRespuestaResponse] = []


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────

class CicloResumen(BaseModel):
    ciclo: str
    label: str
    puntaje_maximo: float
    puntaje_obtenido: float
    porcentaje: float
    total_estandares: int
    cumplen: int
    no_cumplen: int
    no_aplican: int


class DashboardEstandaresMinimos(BaseModel):
    autoevaluacion_id: int
    año: int
    grupo: GrupoEstandar
    num_trabajadores: int
    nivel_riesgo: NivelRiesgoEmpresa
    puntaje_total: float
    nivel_cumplimiento: Optional[NivelCumplimiento] = None
    ciclos: List[CicloResumen]
    total_estandares: int
    total_cumplen: int
    total_no_cumplen: int
    total_no_aplican: int
    estandares_criticos: List[str]   # códigos con NO_CUMPLE
