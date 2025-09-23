from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, field_validator, ValidationInfo

from app.models.worker_vacation import VacationStatus


class VacationBalanceBase(BaseModel):
    year: int
    total_days: int = 15
    used_days: int = 0
    pending_days: int = 0


class VacationBalanceCreate(VacationBalanceBase):
    worker_id: int


class VacationBalanceUpdate(BaseModel):
    total_days: Optional[int] = None
    used_days: Optional[int] = None
    pending_days: Optional[int] = None


class VacationBalance(VacationBalanceBase):
    id: int
    worker_id: int
    available_days: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkerVacationBase(BaseModel):
    start_date: date
    end_date: date
    reason: str

    @field_validator('end_date')
    @classmethod
    def validate_end_date(cls, v, info: ValidationInfo):
        """Valida que la fecha de fin sea posterior a la fecha de inicio"""
        if v and info.data and 'start_date' in info.data and info.data['start_date']:
            if v <= info.data['start_date']:
                raise ValueError('La fecha de fin debe ser posterior a la fecha de inicio')
        return v

    @field_validator('start_date')
    @classmethod
    def validate_start_date(cls, v):
        """Valida que la fecha de inicio no sea anterior a hoy"""
        from datetime import date, timedelta
        # Permitir fechas desde ayer para dar flexibilidad con zonas horarias
        min_date = date.today() - timedelta(days=1)
        if v and v < min_date:
            raise ValueError('La fecha de inicio no puede ser anterior a ayer')
        return v

    @field_validator('reason')
    @classmethod
    def validate_reason(cls, v):
        """Valida que la razón no esté vacía"""
        if not v or not v.strip():
            raise ValueError('La razón es requerida')
        return v.strip()


class WorkerVacationCreate(WorkerVacationBase):
    # worker_id se obtiene del parámetro de la URL, no del body
    pass


class WorkerVacationUpdate(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    reason: Optional[str] = None
    status: Optional[VacationStatus] = None
    rejection_reason: Optional[str] = None

    @field_validator('end_date')
    @classmethod
    def validate_end_date(cls, v, info: ValidationInfo):
        """Valida que la fecha de fin sea posterior a la fecha de inicio"""
        if v and info.data and 'start_date' in info.data and info.data['start_date']:
            if v <= info.data['start_date']:
                raise ValueError('La fecha de fin debe ser posterior a la fecha de inicio')
        return v

    @field_validator('rejection_reason')
    @classmethod
    def validate_rejection_reason(cls, v, info: ValidationInfo):
        """Valida que se proporcione razón de rechazo cuando el estado es rechazado"""
        if info.data and 'status' in info.data and info.data['status'] == VacationStatus.REJECTED:
            if not v or not v.strip():
                raise ValueError('La razón de rechazo es requerida cuando se rechaza una solicitud')
        return v


class WorkerVacation(WorkerVacationBase):
    id: int
    worker_id: int
    days: int
    status: VacationStatus
    request_date: datetime
    requested_by: int
    approved_by: Optional[int] = None
    approved_date: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Información adicional del trabajador y usuarios
    worker_name: Optional[str] = None
    requested_by_name: Optional[str] = None
    approved_by_name: Optional[str] = None

    class Config:
        from_attributes = True


class VacationRequestWithWorker(BaseModel):
    """Esquema para solicitudes de vacaciones con información del trabajador"""
    id: int
    worker_id: int
    worker_name: str
    start_date: date
    end_date: date
    days_requested: int
    reason: str
    status: VacationStatus
    admin_comments: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    is_active: bool

    class Config:
        from_attributes = True


class VacationConflict(BaseModel):
    """Esquema para representar conflictos de fechas de vacaciones"""
    worker_id: int
    worker_name: str
    start_date: date
    end_date: date
    status: VacationStatus
    overlapping_days: int


class VacationAvailability(BaseModel):
    """Esquema para verificar disponibilidad de fechas"""
    start_date: date
    end_date: date
    is_available: bool
    conflicts: List[VacationConflict] = []
    requested_days: int
    available_days: int


class VacationStats(BaseModel):
    """Esquema para estadísticas de vacaciones"""
    total_requests: int
    pending_requests: int
    approved_requests: int
    rejected_requests: int
    total_days_requested: int
    total_days_approved: int
    workers_with_pending: int


class VacationCalendarDay(BaseModel):
    """Esquema para representar un día en el calendario de vacaciones"""
    date: date
    is_available: bool
    workers_on_vacation: List[str] = []
    pending_requests: int = 0


class VacationCalendar(BaseModel):
    """Esquema para el calendario de vacaciones"""
    year: int
    month: int
    days: List[VacationCalendarDay]