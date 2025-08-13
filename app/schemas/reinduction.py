from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field

from app.models.reinduction import ReinductionStatus


class ReinductionRecordBase(BaseModel):
    """Esquema base para registros de reinducción"""
    worker_id: int
    year: int
    due_date: date
    status: ReinductionStatus = ReinductionStatus.PENDING
    assigned_course_id: Optional[int] = None
    scheduled_date: Optional[date] = None
    notes: Optional[str] = None
    exemption_reason: Optional[str] = None


class ReinductionRecordCreate(ReinductionRecordBase):
    """Esquema para crear un registro de reinducción"""
    pass


class ReinductionRecordUpdate(BaseModel):
    """Esquema para actualizar un registro de reinducción"""
    status: Optional[ReinductionStatus] = None
    assigned_course_id: Optional[int] = None
    enrollment_id: Optional[int] = None
    scheduled_date: Optional[date] = None
    completed_date: Optional[date] = None
    notes: Optional[str] = None
    exemption_reason: Optional[str] = None


class ReinductionRecordResponse(ReinductionRecordBase):
    """Esquema de respuesta para registros de reinducción"""
    id: int
    enrollment_id: Optional[int] = None
    completed_date: Optional[date] = None
    first_notification_sent: Optional[datetime] = None
    reminder_notification_sent: Optional[datetime] = None
    overdue_notification_sent: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int] = None
    
    # Propiedades calculadas
    is_overdue: bool
    days_until_due: int
    needs_notification: bool
    
    # Información relacionada
    worker_name: Optional[str] = None
    course_title: Optional[str] = None
    enrollment_status: Optional[str] = None
    
    class Config:
        from_attributes = True


class ReinductionConfigBase(BaseModel):
    """Esquema base para configuración de reinducción"""
    first_notification_days: int = Field(default=60, ge=1, le=365)
    reminder_notification_days: int = Field(default=30, ge=1, le=365)
    grace_period_days: int = Field(default=30, ge=0, le=90)
    default_reinduction_course_id: Optional[int] = None
    auto_enroll_enabled: bool = False
    auto_check_enabled: bool = True
    auto_notification_enabled: bool = True


class ReinductionConfigCreate(ReinductionConfigBase):
    """Esquema para crear configuración de reinducción"""
    pass


class ReinductionConfigUpdate(BaseModel):
    """Esquema para actualizar configuración de reinducción"""
    first_notification_days: Optional[int] = Field(None, ge=1, le=365)
    reminder_notification_days: Optional[int] = Field(None, ge=1, le=365)
    grace_period_days: Optional[int] = Field(None, ge=0, le=90)
    default_reinduction_course_id: Optional[int] = None
    auto_enroll_enabled: Optional[bool] = None
    auto_check_enabled: Optional[bool] = None
    auto_notification_enabled: Optional[bool] = None


class ReinductionConfigResponse(ReinductionConfigBase):
    """Esquema de respuesta para configuración de reinducción"""
    id: int
    created_at: datetime
    updated_at: datetime
    updated_by: Optional[int] = None
    
    # Información relacionada
    default_course_title: Optional[str] = None
    
    class Config:
        from_attributes = True


class WorkerReinductionSummary(BaseModel):
    """Resumen de reinducción para un trabajador"""
    worker_id: int
    worker_name: str
    fecha_de_ingreso: date
    years_in_company: int
    current_year_record: Optional[ReinductionRecordResponse] = None
    total_reinducciones: int
    completed_reinducciones: int
    pending_reinducciones: int
    overdue_reinducciones: int
    next_due_date: Optional[date] = None
    
    class Config:
        from_attributes = True


class ReinductionDashboard(BaseModel):
    """Dashboard con estadísticas de reinducción"""
    total_workers: int
    workers_requiring_reinduction: int
    pending_reinducciones: int
    in_progress_reinducciones: int
    completed_this_year: int
    overdue_reinducciones: int
    upcoming_due_30_days: int
    upcoming_due_60_days: int
    
    # Listas de trabajadores por estado
    workers_overdue: List[WorkerReinductionSummary]
    workers_due_soon: List[WorkerReinductionSummary]
    
    class Config:
        from_attributes = True


class BulkReinductionCreate(BaseModel):
    """Esquema para crear reinducciones en lote"""
    worker_ids: List[int]
    year: int
    assigned_course_id: Optional[int] = None
    scheduled_date: Optional[date] = None
    notes: Optional[str] = None


class BulkReinductionResponse(BaseModel):
    """Respuesta para operaciones en lote"""
    created_count: int
    updated_count: int
    skipped_count: int
    errors: List[str] = []
    created_records: List[ReinductionRecordResponse] = []
    
    class Config:
        from_attributes = True


class ReinductionNotification(BaseModel):
    """Esquema para notificaciones de reinducción"""
    record_id: int
    worker_id: int
    worker_name: str
    worker_email: Optional[str] = None
    notification_type: str  # 'first', 'reminder', 'overdue'
    due_date: date
    days_until_due: int
    message: str
    
    class Config:
        from_attributes = True