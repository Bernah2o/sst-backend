from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, field_validator, ValidationInfo
from enum import Enum

class TipoFecha(str, Enum):
    RANGO = "rango"
    UNICA = "unica"

class EstadoActividad(str, Enum):
    PENDIENTE = "pendiente"
    EN_PROGRESO = "en_progreso"
    COMPLETADA = "completada"
    CANCELADA = "cancelada"

class PrioridadActividad(str, Enum):
    BAJA = "baja"
    MEDIA = "media"
    ALTA = "alta"
    CRITICA = "critica"

class SeguimientoActividadBase(BaseModel):
    titulo: str
    descripcion: Optional[str] = None
    tipo_fecha: TipoFecha
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    fecha_unica: Optional[date] = None
    estado: EstadoActividad = EstadoActividad.PENDIENTE
    prioridad: PrioridadActividad = PrioridadActividad.MEDIA
    responsable: Optional[str] = None
    observaciones: Optional[str] = None

    @field_validator('fecha_inicio', 'fecha_fin', 'fecha_unica')
    @classmethod
    def validate_fechas(cls, v, info: ValidationInfo):
        if not info.data:
            return v
            
        tipo_fecha = info.data.get('tipo_fecha')
        field_name = info.field_name
        
        if tipo_fecha == TipoFecha.RANGO:
            if field_name == 'fecha_unica' and v is not None:
                raise ValueError('No se debe especificar fecha_unica cuando tipo_fecha es "rango"')
            if field_name in ['fecha_inicio', 'fecha_fin'] and v is None:
                raise ValueError('fecha_inicio y fecha_fin son requeridas cuando tipo_fecha es "rango"')
        elif tipo_fecha == TipoFecha.UNICA:
            if field_name in ['fecha_inicio', 'fecha_fin'] and v is not None:
                raise ValueError('No se deben especificar fecha_inicio o fecha_fin cuando tipo_fecha es "unica"')
            if field_name == 'fecha_unica' and v is None:
                raise ValueError('fecha_unica es requerida cuando tipo_fecha es "unica"')
        
        return v

    @field_validator('fecha_fin')
    @classmethod
    def validate_fecha_fin_after_inicio(cls, v, info: ValidationInfo):
        if not info.data:
            return v
            
        fecha_inicio = info.data.get('fecha_inicio')
        if fecha_inicio and v and v < fecha_inicio:
            raise ValueError('fecha_fin debe ser posterior a fecha_inicio')
        return v

class SeguimientoActividadCreate(SeguimientoActividadBase):
    seguimiento_id: int

class SeguimientoActividadUpdate(BaseModel):
    titulo: Optional[str] = None
    descripcion: Optional[str] = None
    tipo_fecha: Optional[TipoFecha] = None
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    fecha_unica: Optional[date] = None
    estado: Optional[EstadoActividad] = None
    prioridad: Optional[PrioridadActividad] = None
    responsable: Optional[str] = None
    observaciones: Optional[str] = None
    completada_por: Optional[int] = None
    fecha_completada: Optional[datetime] = None

class SeguimientoActividadResponse(SeguimientoActividadBase):
    id: int
    seguimiento_id: int
    archivo_soporte_url: Optional[str] = None
    archivo_soporte_nombre: Optional[str] = None
    completada_por: Optional[int] = None
    fecha_completada: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class SeguimientoActividadListResponse(BaseModel):
    id: int
    seguimiento_id: int
    titulo: str
    tipo_fecha: TipoFecha
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    fecha_unica: Optional[date] = None
    estado: EstadoActividad
    prioridad: PrioridadActividad
    responsable: Optional[str] = None
    descripcion: Optional[str] = None
    observaciones: Optional[str] = None
    archivo_soporte_url: Optional[str] = None
    archivo_soporte_nombre: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class ArchivoSoporteResponse(BaseModel):
    url: str
    nombre_archivo: str
    mensaje: str