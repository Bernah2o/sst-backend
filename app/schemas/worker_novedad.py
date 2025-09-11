from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, validator
from decimal import Decimal

from app.models.worker_novedad import NovedadType, NovedadStatus


class WorkerNovedadBase(BaseModel):
    tipo: NovedadType
    titulo: str
    descripcion: Optional[str] = None
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    salario_anterior: Optional[Decimal] = None
    monto_aumento: Optional[Decimal] = None
    cantidad_horas: Optional[Decimal] = None
    valor_hora: Optional[Decimal] = None
    observaciones: Optional[str] = None
    documento_soporte: Optional[str] = None

    @validator('fecha_fin')
    def validate_fecha_fin(cls, v, values):
        """Valida que fecha_fin sea posterior a fecha_inicio"""
        if v and 'fecha_inicio' in values and values['fecha_inicio']:
            if v < values['fecha_inicio']:
                raise ValueError('La fecha de fin debe ser posterior a la fecha de inicio')
        return v

    @validator('monto_aumento')
    def validate_monto_aumento(cls, v, values):
        """Valida que el monto de aumento sea positivo"""
        if v is not None and v <= 0:
            raise ValueError('El monto de aumento debe ser positivo')
        return v

    @validator('cantidad_horas')
    def validate_cantidad_horas(cls, v):
        """Valida que la cantidad de horas sea positiva"""
        if v is not None and v <= 0:
            raise ValueError('La cantidad de horas debe ser positiva')
        return v

    @validator('valor_hora')
    def validate_valor_hora(cls, v):
        """Valida que el valor por hora sea positivo"""
        if v is not None and v <= 0:
            raise ValueError('El valor por hora debe ser positivo')
        return v


class WorkerNovedadCreate(WorkerNovedadBase):
    worker_id: int

    @validator('fecha_inicio')
    def validate_campos_requeridos_por_tipo(cls, v, values):
        """Valida campos requeridos según el tipo de novedad"""
        if 'tipo' in values:
            tipo = values['tipo']
            
            # Tipos que requieren fechas
            tipos_con_fechas = [
                NovedadType.LICENCIA_PATERNIDAD,
                NovedadType.INCAPACIDAD_MEDICA,
                NovedadType.PERMISO_DIA_NO_REMUNERADO,
                NovedadType.LICENCIA_MATERNIDAD
            ]
            
            if tipo in tipos_con_fechas and not v:
                raise ValueError(f'La fecha de inicio es requerida para {tipo.value}')
                
            # Permiso día de la familia solo requiere fecha_inicio
            if tipo == NovedadType.PERMISO_DIA_FAMILIA and not v:
                raise ValueError('La fecha es requerida para permiso día de la familia')
        
        return v

    @validator('salario_anterior')
    def validate_salario_para_aumento(cls, v, values):
        """Valida que se proporcione salario anterior para aumentos"""
        if 'tipo' in values and values['tipo'] == NovedadType.AUMENTO_SALARIO:
            if not v:
                raise ValueError('El salario anterior es requerido para aumentos de salario')
        return v

    @validator('cantidad_horas')
    def validate_horas_para_extras_recargos(cls, v, values):
        """Valida que se proporcionen horas para extras y recargos"""
        if 'tipo' in values and values['tipo'] in [NovedadType.HORAS_EXTRAS, NovedadType.RECARGOS]:
            if not v:
                raise ValueError(f'La cantidad de horas es requerida para {values["tipo"].value}')
        return v


class WorkerNovedadUpdate(BaseModel):
    titulo: Optional[str] = None
    descripcion: Optional[str] = None
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    salario_anterior: Optional[Decimal] = None
    monto_aumento: Optional[Decimal] = None
    cantidad_horas: Optional[Decimal] = None
    valor_hora: Optional[Decimal] = None
    observaciones: Optional[str] = None
    documento_soporte: Optional[str] = None
    status: Optional[NovedadStatus] = None

    @validator('fecha_fin')
    def validate_fecha_fin(cls, v, values):
        """Valida que fecha_fin sea posterior a fecha_inicio"""
        if v and 'fecha_inicio' in values and values['fecha_inicio']:
            if v < values['fecha_inicio']:
                raise ValueError('La fecha de fin debe ser posterior a la fecha de inicio')
        return v


class WorkerNovedadResponse(WorkerNovedadBase):
    id: int
    worker_id: int
    status: NovedadStatus
    dias_calculados: Optional[int] = None
    salario_nuevo: Optional[Decimal] = None
    valor_total: Optional[Decimal] = None
    registrado_por: int
    aprobado_por: Optional[int] = None
    fecha_aprobacion: Optional[datetime] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    # Información adicional del trabajador
    worker_name: Optional[str] = None
    worker_document: Optional[str] = None
    registrado_por_name: Optional[str] = None
    aprobado_por_name: Optional[str] = None

    class Config:
        from_attributes = True


class WorkerNovedadList(BaseModel):
    id: int
    worker_id: int
    worker_name: str
    worker_document: str
    tipo: NovedadType
    titulo: str
    status: NovedadStatus
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    dias_calculados: Optional[int] = None
    monto_aumento: Optional[Decimal] = None
    valor_total: Optional[Decimal] = None
    registrado_por_name: str
    aprobado_por_name: Optional[str] = None
    fecha_aprobacion: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class WorkerNovedadApproval(BaseModel):
    """Esquema para aprobar/rechazar novedades"""
    status: NovedadStatus
    observaciones: Optional[str] = None

    @validator('status')
    def validate_status(cls, v):
        """Valida que el status sea válido para aprobación"""
        if v not in [NovedadStatus.APROBADA, NovedadStatus.RECHAZADA]:
            raise ValueError('El status debe ser APROBADA o RECHAZADA')
        return v


class WorkerNovedadStats(BaseModel):
    """Esquema para estadísticas de novedades"""
    total_novedades: int
    pendientes: int
    aprobadas: int
    rechazadas: int
    procesadas: int
    por_tipo: dict
    
    class Config:
        from_attributes = True