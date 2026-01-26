from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.models.restriccion_medica import EstadoImplementacion, TipoRestriccion


class RestriccionMedicaBase(BaseModel):
    worker_id: int
    occupational_exam_id: Optional[int] = None
    tipo_restriccion: TipoRestriccion
    descripcion: str
    actividades_restringidas: Optional[str] = None
    recomendaciones: Optional[str] = None
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    responsable_implementacion_id: Optional[int] = None

    @model_validator(mode="after")
    def validate_fechas_por_tipo(self):
        if self.tipo_restriccion == TipoRestriccion.PERMANENTE and self.fecha_fin is not None:
            raise ValueError("fecha_fin debe ser null si tipo_restriccion='permanente'")
        return self


class RestriccionMedicaCreate(RestriccionMedicaBase):
    pass


class RestriccionMedicaUpdate(BaseModel):
    tipo_restriccion: Optional[TipoRestriccion] = None
    descripcion: Optional[str] = None
    actividades_restringidas: Optional[str] = None
    recomendaciones: Optional[str] = None
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    activa: Optional[bool] = None
    responsable_implementacion_id: Optional[int] = None

    @model_validator(mode="after")
    def validate_fechas_por_tipo(self):
        if self.tipo_restriccion == TipoRestriccion.PERMANENTE and self.fecha_fin is not None:
            raise ValueError("fecha_fin debe ser null si tipo_restriccion='permanente'")
        return self


class RestriccionMedicaImplementar(BaseModel):
    observaciones_implementacion: Optional[str] = None
    fecha_implementacion: Optional[date] = None


class RestriccionMedicaResponse(BaseModel):
    id: int
    worker_id: int
    occupational_exam_id: Optional[int] = None
    tipo_restriccion: TipoRestriccion
    descripcion: str
    actividades_restringidas: Optional[str] = None
    recomendaciones: Optional[str] = None
    fecha_inicio: date
    fecha_fin: Optional[date] = None
    activa: bool
    fecha_limite_implementacion: date
    fecha_implementacion: Optional[date] = None
    estado_implementacion: EstadoImplementacion
    implementada: bool
    responsable_implementacion_id: Optional[int] = None
    observaciones_implementacion: Optional[str] = None
    creado_por: Optional[int] = None
    fecha_creacion: datetime
    modificado_por: Optional[int] = None
    fecha_modificacion: Optional[datetime] = None
    dias_para_implementar: int = Field(..., description="Días restantes para implementar; negativo si vencida")
    esta_vencida: bool

    class Config:
        from_attributes = True

