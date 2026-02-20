from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date


# ── Seguimiento ────────────────────────────────────────────────────────────────

class CapacitacionSeguimientoUpdate(BaseModel):
    programada: Optional[bool] = None
    ejecutada: Optional[bool] = None
    observacion: Optional[str] = None
    fecha_ejecucion: Optional[date] = None
    ejecutado_por: Optional[str] = None
    trabajadores_programados: Optional[int] = None
    trabajadores_participaron: Optional[int] = None
    personas_evaluadas: Optional[int] = None
    evaluaciones_eficaces: Optional[int] = None


class CapacitacionSeguimientoResponse(BaseModel):
    id: int
    actividad_id: int
    mes: int
    programada: bool
    ejecutada: bool
    observacion: Optional[str] = None
    fecha_ejecucion: Optional[date] = None
    ejecutado_por: Optional[str] = None
    trabajadores_programados: int
    trabajadores_participaron: int
    personas_evaluadas: int
    evaluaciones_eficaces: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Actividad ──────────────────────────────────────────────────────────────────

class CapacitacionActividadCreate(BaseModel):
    ciclo: str
    nombre: str
    encargado: Optional[str] = None
    recursos: Optional[str] = None
    horas: Optional[float] = 0
    orden: int = 0


class CapacitacionActividadUpdate(BaseModel):
    nombre: Optional[str] = None
    encargado: Optional[str] = None
    recursos: Optional[str] = None
    horas: Optional[float] = None
    orden: Optional[int] = None


class CapacitacionActividadResponse(BaseModel):
    id: int
    programa_id: int
    ciclo: str
    nombre: str
    encargado: Optional[str] = None
    recursos: Optional[str] = None
    horas: Optional[float] = None
    orden: int
    seguimientos: List[CapacitacionSeguimientoResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Indicador Mensual ──────────────────────────────────────────────────────────

class IndicadorMensualUpdate(BaseModel):
    numerador: Optional[float] = None
    denominador: Optional[float] = None
    analisis_trimestral: Optional[str] = None


class IndicadorMensualResponse(BaseModel):
    id: int
    programa_id: int
    tipo_indicador: str
    mes: int
    numerador: float
    denominador: float
    valor_porcentaje: float
    meta: Optional[float] = None
    analisis_trimestral: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Programa Principal ─────────────────────────────────────────────────────────

class ProgramaCapacitacionesCreate(BaseModel):
    año: int
    empresa_id: Optional[int] = None
    codigo: str = "PR-SST-01"
    version: str = "1"
    titulo: str = "PROGRAMA DE CAPACITACIONES"
    alcance: Optional[str] = None
    objetivo: Optional[str] = None
    recursos: Optional[str] = None
    meta_cumplimiento: float = 90.0
    meta_cobertura: float = 80.0
    meta_eficacia: float = 90.0
    encargado_sgsst: Optional[str] = None
    aprobado_por: Optional[str] = None
    estado: str = "borrador"


class ProgramaCapacitacionesUpdate(BaseModel):
    codigo: Optional[str] = None
    version: Optional[str] = None
    titulo: Optional[str] = None
    alcance: Optional[str] = None
    objetivo: Optional[str] = None
    recursos: Optional[str] = None
    meta_cumplimiento: Optional[float] = None
    meta_cobertura: Optional[float] = None
    meta_eficacia: Optional[float] = None
    encargado_sgsst: Optional[str] = None
    aprobado_por: Optional[str] = None
    estado: Optional[str] = None


class ProgramaCapacitacionesResponse(BaseModel):
    id: int
    año: int
    empresa_id: Optional[int] = None
    codigo: str
    version: str
    titulo: str
    alcance: Optional[str] = None
    objetivo: Optional[str] = None
    recursos: Optional[str] = None
    meta_cumplimiento: float
    meta_cobertura: float
    meta_eficacia: float
    encargado_sgsst: Optional[str] = None
    aprobado_por: Optional[str] = None
    estado: str
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProgramaCapacitacionesDetailResponse(ProgramaCapacitacionesResponse):
    actividades: List[CapacitacionActividadResponse] = []


# ── Dashboard / KPIs ───────────────────────────────────────────────────────────

class KpiMesData(BaseModel):
    mes: int
    nombre_mes: str
    valor: float
    meta: float
    numerador: float
    denominador: float
    cumple: bool


class KpiIndicador(BaseModel):
    tipo: str
    nombre: str
    formula: str
    meta: float
    frecuencia: str
    meses: List[KpiMesData]
    valor_global: float
    cumple_global: bool
    analisis_t1: Optional[str] = None
    analisis_t2: Optional[str] = None
    analisis_t3: Optional[str] = None
    analisis_t4: Optional[str] = None


class DashboardCapacitaciones(BaseModel):
    programa_id: int
    año: int
    total_actividades: int
    actividades_programadas: int
    actividades_ejecutadas: int
    porcentaje_cumplimiento: float
    kpis: List[KpiIndicador]
