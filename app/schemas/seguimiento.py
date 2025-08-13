from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel
from app.models.seguimiento import EstadoSeguimiento, ValoracionRiesgo

class SeguimientoBase(BaseModel):
    worker_id: int
    programa: str
    nombre_trabajador: str
    cedula: str
    cargo: str
    fecha_ingreso: Optional[date] = None
    estado: EstadoSeguimiento = EstadoSeguimiento.INICIADO
    valoracion_riesgo: Optional[ValoracionRiesgo] = None
    fecha_inicio: Optional[date] = None
    fecha_final: Optional[date] = None
    observacion: Optional[str] = None
    motivo_inclusion: Optional[str] = None
    conclusiones_ocupacionales: Optional[str] = None
    conductas_ocupacionales_prevenir: Optional[str] = None
    recomendaciones_generales: Optional[str] = None
    observaciones_examen: Optional[str] = None
    comentario: Optional[str] = None

class SeguimientoCreate(SeguimientoBase):
    pass

class SeguimientoUpdate(BaseModel):
    estado: Optional[EstadoSeguimiento] = None
    valoracion_riesgo: Optional[ValoracionRiesgo] = None
    fecha_inicio: Optional[date] = None
    fecha_final: Optional[date] = None
    observacion: Optional[str] = None
    motivo_inclusion: Optional[str] = None
    conclusiones_ocupacionales: Optional[str] = None
    conductas_ocupacionales_prevenir: Optional[str] = None
    recomendaciones_generales: Optional[str] = None
    observaciones_examen: Optional[str] = None
    comentario: Optional[str] = None

class SeguimientoResponse(SeguimientoBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class SeguimientoListResponse(BaseModel):
    id: int
    worker_id: int
    programa: str
    nombre_trabajador: str
    cedula: str
    cargo: str
    estado: EstadoSeguimiento
    valoracion_riesgo: Optional[ValoracionRiesgo] = None
    fecha_inicio: Optional[date] = None
    fecha_final: Optional[date] = None
    created_at: datetime
    
    class Config:
        from_attributes = True