from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date


class CronogramaPypSeguimientoBase(BaseModel):
    mes: int
    programada: bool = False
    ejecutada: bool = False
    observacion: Optional[str] = None
    fecha_ejecucion: Optional[date] = None
    ejecutado_por: Optional[str] = None


class CronogramaPypSeguimientoUpdate(BaseModel):
    programada: Optional[bool] = None
    ejecutada: Optional[bool] = None
    observacion: Optional[str] = None
    fecha_ejecucion: Optional[date] = None
    ejecutado_por: Optional[str] = None


class CronogramaPypSeguimientoResponse(CronogramaPypSeguimientoBase):
    id: int
    actividad_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CronogramaPypActividadBase(BaseModel):
    actividad: str
    poblacion_objetivo: Optional[str] = None
    responsable: Optional[str] = None
    indicador: Optional[str] = None
    recursos: Optional[str] = None
    observaciones: Optional[str] = None
    orden: int = 0


class CronogramaPypActividadCreate(CronogramaPypActividadBase):
    pass


class CronogramaPypActividadUpdate(BaseModel):
    actividad: Optional[str] = None
    poblacion_objetivo: Optional[str] = None
    responsable: Optional[str] = None
    indicador: Optional[str] = None
    recursos: Optional[str] = None
    observaciones: Optional[str] = None
    orden: Optional[int] = None


class CronogramaPypActividadResponse(CronogramaPypActividadBase):
    id: int
    cronograma_id: int
    seguimientos_mensuales: List[CronogramaPypSeguimientoResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CronogramaPypBase(BaseModel):
    codigo: str = "CR-PYP-01"
    version: str = "1"
    objetivo: Optional[str] = (
        "Planificar y controlar la ejecución de actividades del Programa de Promoción y Prevención (PYP)"
    )
    alcance: Optional[str] = (
        "Aplica para los trabajadores, contratistas y subcontratistas de la Empresa"
    )
    encargado_sgsst: Optional[str] = None
    aprobado_por: Optional[str] = None


class CronogramaPypCreate(CronogramaPypBase):
    pass


class CronogramaPypUpdate(BaseModel):
    codigo: Optional[str] = None
    version: Optional[str] = None
    objetivo: Optional[str] = None
    alcance: Optional[str] = None
    encargado_sgsst: Optional[str] = None
    aprobado_por: Optional[str] = None


class CronogramaPypResponse(CronogramaPypBase):
    id: int
    plan_trabajo_anual_id: int
    año: int
    empresa_id: Optional[int] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CronogramaPypDetailResponse(CronogramaPypResponse):
    actividades: List[CronogramaPypActividadResponse] = []

