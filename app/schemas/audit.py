from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

from app.models.audit import AuditAction


class AuditLogBase(BaseModel):
    action: AuditAction
    resource_type: str
    resource_id: Optional[int] = None
    resource_name: Optional[str] = None
    old_values: Optional[str] = None
    new_values: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    details: Optional[str] = None
    success: str = "true"
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None


class AuditLogCreate(AuditLogBase):
    user_id: Optional[int] = None


class AuditLogResponse(AuditLogBase):
    id: int
    user_id: Optional[int] = None
    created_at: datetime
    
    # User information (if available)
    user_name: Optional[str] = None
    user_email: Optional[str] = None

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    items: List[AuditLogResponse]
    total: int
    page: int
    limit: int
    total_pages: int

    class Config:
        from_attributes = True