from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, field_validator, ValidationInfo, model_validator

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
    comments: Optional[str] = None
    allow_past_dates: Optional[bool] = False  # Administrative override

    @field_validator('end_date')
    @classmethod
    def validate_end_date(cls, v, info: ValidationInfo):
        """Valida que la fecha de fin sea posterior a la fecha de inicio"""
        if v and info.data and 'start_date' in info.data and info.data['start_date']:
            if v <= info.data['start_date']:
                raise ValueError('La fecha de fin debe ser posterior a la fecha de inicio')
        return v

    @model_validator(mode='after')
    def validate_start_date_with_override(self):
        """Valida que la fecha de inicio no sea anterior a hoy, con override administrativo"""
        from datetime import date, timedelta
        import logging
        
        # Check if administrative override is enabled
        if getattr(self, 'allow_past_dates', False):
            logging.info(f"Administrative override enabled - allowing past date: {self.start_date}")
            return self
        
        # Skip validation if this is data being read from database (has id field)
        if hasattr(self, 'id') and getattr(self, 'id', None) is not None:
            logging.info(f"Skipping date validation for existing record with id: {self.id}")
            return self
        
        # Permitir fechas desde ayer para dar flexibilidad con zonas horarias
        today = date.today()
        min_date = today - timedelta(days=1)
        
        # Log para debugging
        logging.info(f"Validating start_date: {self.start_date}, today: {today}, min_date: {min_date}")
        
        if self.start_date and self.start_date < min_date:
            logging.warning(f"Date validation failed: {self.start_date} < {min_date}")
            raise ValueError('La fecha de inicio no puede ser anterior a ayer')
        return self

    @field_validator('comments')
    @classmethod
    def validate_comments(cls, v):
        """Valida que los comentarios no estén vacíos si se proporcionan"""
        if v is not None and not v.strip():
            return None  # Convertir string vacío a None
        return v.strip() if v else v


class WorkerVacationCreate(WorkerVacationBase):
    # worker_id se obtiene del parámetro de la URL, no del body
    pass


class WorkerVacationUpdate(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    comments: Optional[str] = None
    status: Optional[VacationStatus] = None

    @field_validator('start_date')
    @classmethod
    def validate_start_date(cls, v):
        """Valida que la fecha de inicio no sea anterior a hoy"""
        if v is None:  # Skip validation if no start_date is provided
            return v
            
        from datetime import date, timedelta
        import logging
        
        # Permitir fechas desde ayer para dar flexibilidad con zonas horarias
        today = date.today()
        min_date = today - timedelta(days=1)
        
        # Log para debugging
        logging.info(f"Validating update start_date: {v}, today: {today}, min_date: {min_date}")
        
        if v < min_date:
            logging.warning(f"Update date validation failed: {v} < {min_date}")
            raise ValueError('La fecha de inicio no puede ser anterior a ayer')
        return v

    @field_validator('end_date')
    @classmethod
    def validate_end_date(cls, v, info: ValidationInfo):
        """Valida que la fecha de fin sea posterior a la fecha de inicio"""
        if v and info.data and 'start_date' in info.data and info.data['start_date']:
            if v <= info.data['start_date']:
                raise ValueError('La fecha de fin debe ser posterior a la fecha de inicio')
        return v


class WorkerVacation(WorkerVacationBase):
    id: int
    worker_id: int
    days_requested: int
    comments: Optional[str] = None
    status: VacationStatus
    request_date: datetime
    approved_by: Optional[int] = None
    approved_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # Información adicional del trabajador y usuarios
    worker_name: Optional[str] = None
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
    comments: Optional[str] = None
    status: VacationStatus
    created_at: datetime
    updated_at: datetime
    approved_by: Optional[int] = None
    approved_date: Optional[datetime] = None

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