from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date

from app.models.programa_inspecciones import (
    EstadoPrograma, TipoInspeccion, FrecuenciaInspeccion, CicloInspeccion
)


# ---- Seguimiento Mensual ----

class InspeccionSeguimientoBase(BaseModel):
    mes: int
    programada: bool = False
    ejecutada: bool = False
    condiciones_peligrosas_reportadas: int = 0
    condiciones_peligrosas_intervenidas: int = 0
    fecha_ejecucion: Optional[date] = None
    ejecutado_por: Optional[str] = None
    hallazgos: Optional[str] = None
    accion_correctiva: Optional[str] = None
    observacion: Optional[str] = None


class InspeccionSeguimientoUpdate(BaseModel):
    programada: Optional[bool] = None
    ejecutada: Optional[bool] = None
    condiciones_peligrosas_reportadas: Optional[int] = None
    condiciones_peligrosas_intervenidas: Optional[int] = None
    fecha_ejecucion: Optional[date] = None
    ejecutado_por: Optional[str] = None
    hallazgos: Optional[str] = None
    accion_correctiva: Optional[str] = None
    observacion: Optional[str] = None


class InspeccionSeguimientoResponse(InspeccionSeguimientoBase):
    id: int
    inspeccion_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---- Inspección Programada ----

class InspeccionProgramadaBase(BaseModel):
    ciclo: CicloInspeccion = CicloInspeccion.HACER
    tipo_inspeccion: TipoInspeccion
    area: str
    descripcion: str
    responsable: Optional[str] = None
    frecuencia: FrecuenciaInspeccion = FrecuenciaInspeccion.MENSUAL
    lista_chequeo: Optional[str] = None
    observaciones: Optional[str] = None
    orden: int = 0


class InspeccionProgramadaCreate(InspeccionProgramadaBase):
    pass


class InspeccionProgramadaUpdate(BaseModel):
    ciclo: Optional[CicloInspeccion] = None
    tipo_inspeccion: Optional[TipoInspeccion] = None
    area: Optional[str] = None
    descripcion: Optional[str] = None
    responsable: Optional[str] = None
    frecuencia: Optional[FrecuenciaInspeccion] = None
    lista_chequeo: Optional[str] = None
    observaciones: Optional[str] = None
    orden: Optional[int] = None


class InspeccionProgramadaResponse(InspeccionProgramadaBase):
    id: int
    programa_id: int
    seguimientos: List[InspeccionSeguimientoResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---- Indicadores ----

class IndicadorMes(BaseModel):
    mes: int
    nombre_mes: str
    programadas: int
    ejecutadas: int
    pct_cumplimiento: float
    condiciones_reportadas: int
    condiciones_intervenidas: int
    pct_eficacia: float


class IndicadoresPrograma(BaseModel):
    total_programadas: int
    total_ejecutadas: int
    pct_cumplimiento_global: float
    total_condiciones_reportadas: int
    total_condiciones_intervenidas: int
    pct_eficacia_global: float
    meses: List[IndicadorMes]


# ---- Programa de Inspecciones ----

class ProgramaInspeccionesBase(BaseModel):
    año: int
    empresa_id: Optional[int] = None
    codigo: str = "PR-SST-02"
    version: str = "1"
    objetivo: Optional[str] = None
    alcance: Optional[str] = None
    recursos: Optional[str] = "Económicos, Técnicos, Humanos, Infraestructura"
    legislacion_aplicable: Optional[str] = None
    encargado_sgsst: Optional[str] = None
    aprobado_por: Optional[str] = None
    estado: EstadoPrograma = EstadoPrograma.BORRADOR


class ProgramaInspeccionesCreate(ProgramaInspeccionesBase):
    pass


class ProgramaInspeccionesUpdate(BaseModel):
    codigo: Optional[str] = None
    version: Optional[str] = None
    objetivo: Optional[str] = None
    alcance: Optional[str] = None
    recursos: Optional[str] = None
    legislacion_aplicable: Optional[str] = None
    encargado_sgsst: Optional[str] = None
    aprobado_por: Optional[str] = None
    estado: Optional[EstadoPrograma] = None


class ProgramaInspeccionesResponse(ProgramaInspeccionesBase):
    id: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProgramaInspeccionesDetailResponse(ProgramaInspeccionesResponse):
    inspecciones: List[InspeccionProgramadaResponse] = []
