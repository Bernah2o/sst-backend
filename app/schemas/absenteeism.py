from datetime import date
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, computed_field
from app.models.absenteeism import EventMonth, EventType


class AbsenteeismBase(BaseModel):
    """Esquema base para Absenteeism"""
    event_month: EventMonth = Field(..., description="Mes del evento")
    worker_id: int = Field(..., description="ID del trabajador")
    event_type: EventType = Field(..., description="Tipo de evento")
    start_date: date = Field(..., description="Fecha inicial del periodo de incapacidad")
    end_date: date = Field(..., description="Fecha final del periodo de incapacidad")
    disability_days: int = Field(..., ge=0, description="Días de incapacidad")
    extension: int = Field(default=0, ge=0, description="Prórroga en días")
    charged_days: int = Field(default=0, ge=0, description="Días cargados")
    disability_or_charged_days: int = Field(..., ge=0, description="Días de incapacidad o días cargados")
    diagnostic_code: str = Field(..., max_length=20, description="Código diagnóstico")
    health_condition_description: str = Field(..., description="Descripción de la categoría de la condición de salud")
    observations: Optional[str] = Field(None, description="Observaciones")
    insured_costs_at: Decimal = Field(default=Decimal('0.00'), ge=0, description="Costos asegurados A.T.")
    insured_costs_ac_eg: Decimal = Field(default=Decimal('0.00'), ge=0, description="Costos asegurados A.C. - E.G.")
    assumed_costs_at: Decimal = Field(default=Decimal('0.00'), ge=0, description="Costos asumidos A.T.")
    assumed_costs_ac_eg: Decimal = Field(default=Decimal('0.00'), ge=0, description="Costos asumidos A.C. - E.G.")


class AbsenteeismCreate(AbsenteeismBase):
    """Esquema para crear un nuevo registro de ausentismo"""
    pass


class AbsenteeismUpdate(BaseModel):
    """Esquema para actualizar un registro de ausentismo"""
    event_month: Optional[EventMonth] = None
    worker_id: Optional[int] = None
    event_type: Optional[EventType] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    disability_days: Optional[int] = Field(None, ge=0)
    extension: Optional[int] = Field(None, ge=0)
    charged_days: Optional[int] = Field(None, ge=0)
    disability_or_charged_days: Optional[int] = Field(None, ge=0)
    diagnostic_code: Optional[str] = Field(None, max_length=20)
    health_condition_description: Optional[str] = None
    observations: Optional[str] = None
    insured_costs_at: Optional[Decimal] = Field(None, ge=0)
    insured_costs_ac_eg: Optional[Decimal] = Field(None, ge=0)
    assumed_costs_at: Optional[Decimal] = Field(None, ge=0)
    assumed_costs_ac_eg: Optional[Decimal] = Field(None, ge=0)


class AbsenteeismResponse(AbsenteeismBase):
    """Esquema de respuesta para Absenteeism con campos calculados"""
    id: int
    
    # Campos calculados del trabajador
    cedula: Optional[str] = Field(None, description="Cédula del trabajador")
    cargo: Optional[str] = Field(None, description="Cargo del trabajador")
    base_salary: Optional[Decimal] = Field(None, description="Salario base del trabajador")
    
    @computed_field
    @property
    def daily_base_salary(self) -> Decimal:
        """Calcula el salario base diario (salario / 30 días)"""
        if self.base_salary:
            return self.base_salary / 30
        return Decimal('0.00')
    
    @computed_field
    @property
    def total_disability_days(self) -> int:
        """Calcula el total de días de incapacidad entre fecha inicial y final"""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return 0
    
    class Config:
        from_attributes = True


class AbsenteeismWithWorker(AbsenteeismResponse):
    """Esquema de respuesta para Absenteeism con información del trabajador"""
    worker_name: Optional[str] = Field(None, description="Nombre completo del trabajador")
    worker_email: Optional[str] = Field(None, description="Email del trabajador")
    worker_phone: Optional[str] = Field(None, description="Teléfono del trabajador")


class AbsenteeismList(BaseModel):
    """Esquema para listado paginado de registros de ausentismo"""
    items: list[AbsenteeismWithWorker]
    total: int
    page: int
    size: int
    pages: int


class AbsenteeismStats(BaseModel):
    """Esquema para estadísticas de ausentismo"""
    total_records: int
    total_disability_days: int
    total_costs_at: Decimal
    total_costs_ac_eg: Decimal
    by_event_type: dict[str, int]
    by_month: dict[str, int]