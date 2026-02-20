from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal

from app.models.plan_trabajo_anual import EstadoPlan, CicloPhva, CategoriaActividad


# ---------- Seguimiento Mensual ----------

class PlanTrabajoSeguimientoBase(BaseModel):
    mes: int
    programada: bool = False
    ejecutada: bool = False
    observacion: Optional[str] = None
    fecha_ejecucion: Optional[date] = None
    ejecutado_por: Optional[str] = None


class PlanTrabajoSeguimientoUpdate(BaseModel):
    programada: Optional[bool] = None
    ejecutada: Optional[bool] = None
    observacion: Optional[str] = None
    fecha_ejecucion: Optional[date] = None
    ejecutado_por: Optional[str] = None


class PlanTrabajoSeguimientoResponse(PlanTrabajoSeguimientoBase):
    id: int
    actividad_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------- Actividad ----------

class PlanTrabajoActividadBase(BaseModel):
    ciclo: CicloPhva
    categoria: CategoriaActividad
    estandar: Optional[str] = None
    descripcion: str
    frecuencia: Optional[str] = None
    responsable: Optional[str] = None
    recurso_financiero: bool = False
    recurso_tecnico: bool = False
    costo: Optional[Decimal] = None
    observaciones: Optional[str] = None
    orden: int = 0


class PlanTrabajoActividadCreate(PlanTrabajoActividadBase):
    pass


class PlanTrabajoActividadUpdate(BaseModel):
    estandar: Optional[str] = None
    descripcion: Optional[str] = None
    frecuencia: Optional[str] = None
    responsable: Optional[str] = None
    recurso_financiero: Optional[bool] = None
    recurso_tecnico: Optional[bool] = None
    costo: Optional[Decimal] = None
    observaciones: Optional[str] = None
    orden: Optional[int] = None


class PlanTrabajoActividadResponse(PlanTrabajoActividadBase):
    id: int
    plan_id: int
    seguimientos_mensuales: List[PlanTrabajoSeguimientoResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------- Plan de Trabajo Anual ----------

class PlanTrabajoAnualBase(BaseModel):
    año: int
    empresa_id: Optional[int] = None
    codigo: str = "PL-SST-02"
    version: str = "1"
    objetivo: Optional[str] = "Planear y controlar la ejecución de actividades de seguridad y salud en el trabajo"
    alcance: Optional[str] = "Aplica para los empleados, contratistas y subcontratistas de la Empresa"
    meta: Optional[str] = "Garantizar el cumplimiento del 95% de las actividades programadas en el Plan de Trabajo anual"
    meta_porcentaje: float = 90.0
    indicador: Optional[str] = "(Numero de actividades ejecutadas / numero de actividades programadas) * 100"
    formula: Optional[str] = "N° de Actividades Programadas / N° de Actividades Ejecutadas"
    encargado_sgsst: Optional[str] = None
    aprobado_por: Optional[str] = None
    estado: EstadoPlan = EstadoPlan.BORRADOR


class PlanTrabajoAnualCreate(PlanTrabajoAnualBase):
    pass


class PlanTrabajoAnualUpdate(BaseModel):
    codigo: Optional[str] = None
    version: Optional[str] = None
    objetivo: Optional[str] = None
    alcance: Optional[str] = None
    meta: Optional[str] = None
    meta_porcentaje: Optional[float] = None
    indicador: Optional[str] = None
    formula: Optional[str] = None
    encargado_sgsst: Optional[str] = None
    aprobado_por: Optional[str] = None
    estado: Optional[EstadoPlan] = None


class PlanTrabajoAnualResponse(PlanTrabajoAnualBase):
    id: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PlanTrabajoAnualDetailResponse(PlanTrabajoAnualResponse):
    actividades: List[PlanTrabajoActividadResponse] = []


# ---------- Dashboard / Indicadores ----------

class MesIndicador(BaseModel):
    mes: int
    nombre_mes: str
    programadas: int
    ejecutadas: int
    porcentaje: float


class DashboardIndicadores(BaseModel):
    plan_id: int
    año: int
    meta_porcentaje: float
    total_programadas: int
    total_ejecutadas: int
    porcentaje_global: float
    meses: List[MesIndicador]
    analisis_t1: Optional[str] = None
    analisis_t2: Optional[str] = None
    analisis_t3: Optional[str] = None
    analisis_t4: Optional[str] = None
