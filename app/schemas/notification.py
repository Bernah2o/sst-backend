from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


class NotificationType(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    IN_APP = "in_app"
    PUSH = "push"


class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    READ = "read"


class NotificationPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


# Notification Template Schemas
class NotificationTemplateBase(BaseModel):
    name: str = Field(..., max_length=100)
    subject_template: str = Field(..., max_length=255)
    body_template: str
    notification_type: NotificationType
    is_active: bool = True
    variables: Optional[str] = None  # JSON array
    description: Optional[str] = None


class NotificationTemplateCreate(NotificationTemplateBase):
    pass


class NotificationTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    subject_template: Optional[str] = Field(None, max_length=255)
    body_template: Optional[str] = None
    notification_type: Optional[NotificationType] = None
    is_active: Optional[bool] = None
    variables: Optional[str] = None
    description: Optional[str] = None


class NotificationTemplateResponse(NotificationTemplateBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Notification Schemas
class NotificationBase(BaseModel):
    user_id: int
    title: str = Field(..., max_length=255)
    message: str
    notification_type: NotificationType
    priority: NotificationPriority = NotificationPriority.NORMAL
    scheduled_at: Optional[datetime] = None
    additional_data: Optional[str] = None  # JSON string


class NotificationCreate(NotificationBase):
    pass


class NotificationUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    message: Optional[str] = None
    notification_type: Optional[NotificationType] = None
    status: Optional[NotificationStatus] = None
    priority: Optional[NotificationPriority] = None
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    error_message: Optional[str] = None
    additional_data: Optional[str] = None


class NotificationResponse(NotificationBase):
    id: int
    status: NotificationStatus
    sent_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    id: int
    title: str
    message: str
    notification_type: NotificationType
    status: NotificationStatus
    priority: NotificationPriority
    sent_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Bulk Notification Schema
class BulkNotificationCreate(BaseModel):
    user_ids: Optional[list[int]] = None
    user_roles: Optional[list[str]] = None  # Para enviar por roles específicos
    title: str = Field(..., max_length=255)
    message: str
    notification_type: NotificationType
    priority: NotificationPriority = NotificationPriority.NORMAL
    scheduled_at: Optional[datetime] = None
    template_name: Optional[str] = None
    template_variables: Optional[dict] = None


# Notification Preferences Schema
class NotificationPreferences(BaseModel):
    email_enabled: bool = True
    sms_enabled: bool = True
    in_app_enabled: bool = True
    push_enabled: bool = True
    course_reminders: bool = True
    evaluation_reminders: bool = True
    certificate_notifications: bool = True
    survey_invitations: bool = True