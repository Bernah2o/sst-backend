from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    SUPPRESSED = "suppressed"


class NotificationTypeEnum(str, Enum):
    FIRST_NOTIFICATION = "first_notification"
    REMINDER = "reminder"
    OVERDUE = "overdue"


class ExamStatus(str, Enum):
    SIN_EXAMENES = "sin_examenes"
    VENCIDO = "vencido"
    PROXIMO_A_VENCER = "proximo_a_vencer"
    AL_DIA = "al_dia"


class WorkerExamNotificationBase(BaseModel):
    worker_id: int
    worker_name: str
    worker_document: str
    worker_position: str
    worker_email: Optional[str]
    last_exam_date: Optional[date]
    next_exam_date: date
    days_until_exam: int
    exam_status: ExamStatus
    periodicidad: str
    notification_status: NotificationStatus
    last_notification_sent: Optional[datetime]
    acknowledgment_count: int = 0


class WorkerExamNotificationResponse(WorkerExamNotificationBase):
    can_send_notification: bool
    notification_types_sent: List[str] = []
    last_acknowledgment_date: Optional[datetime]
    
    def __init__(self, **data):
        # Asegurar que notification_types_sent siempre sea una lista
        if 'notification_types_sent' not in data or data['notification_types_sent'] is None:
            data['notification_types_sent'] = []
        super().__init__(**data)
    
    class Config:
        from_attributes = True


class NotificationSendRequest(BaseModel):
    worker_ids: List[int]
    notification_type: NotificationTypeEnum
    force_send: bool = False  # Para enviar aunque ya haya confirmación


class NotificationSendResponse(BaseModel):
    total_requested: int
    emails_sent: int
    emails_failed: int
    already_acknowledged: int
    invalid_workers: int
    details: List[dict] = []


class NotificationSuppressionRequest(BaseModel):
    worker_ids: List[int]
    notification_type: Optional[NotificationTypeEnum] = None  # Si es None, suprime todos los tipos
    reason: Optional[str] = None


class NotificationSuppressionResponse(BaseModel):
    total_requested: int
    suppressions_created: int
    already_suppressed: int
    details: List[dict] = []


class NotificationAcknowledgmentResponse(BaseModel):
    id: int
    worker_id: int
    worker_name: str
    occupational_exam_id: Optional[int]
    notification_type: str
    acknowledged_at: datetime
    ip_address: Optional[str]
    user_agent: Optional[str]
    stops_notifications: bool
    
    class Config:
        from_attributes = True


class NotificationStatistics(BaseModel):
    total_workers: int
    workers_without_exams: int
    workers_with_overdue_exams: int
    workers_with_upcoming_exams: int
    total_notifications_sent_today: int
    total_acknowledgments_today: int
    suppressed_notifications: int


class NotificationFilters(BaseModel):
    exam_status: Optional[ExamStatus] = None
    notification_status: Optional[NotificationStatus] = None
    position: Optional[str] = None
    days_until_exam_min: Optional[int] = None
    days_until_exam_max: Optional[int] = None
    has_email: Optional[bool] = None
    acknowledged: Optional[bool] = None


class BulkNotificationAction(BaseModel):
    action: str  # "send", "suppress", "unsuppress"
    worker_ids: List[int]
    notification_type: Optional[NotificationTypeEnum] = None
    force: bool = False
    reason: Optional[str] = None


class BulkNotificationResponse(BaseModel):
    action: str
    total_requested: int
    successful: int
    failed: int
    skipped: int
    details: List[dict] = []