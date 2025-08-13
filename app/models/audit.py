from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class AuditAction(str, Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    EXPORT = "export"
    IMPORT = "import"
    DOWNLOAD = "download"
    UPLOAD = "upload"
    APPROVE = "approve"
    REJECT = "reject"
    SUBMIT = "submit"
    COMPLETE = "complete"
    CANCEL = "cancel"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Nullable for system actions
    action = Column(SQLEnum(AuditAction), nullable=False)
    resource_type = Column(String(100), nullable=False)  # e.g., 'user', 'course', 'evaluation'
    resource_id = Column(Integer)  # ID of the affected resource
    resource_name = Column(String(255))  # Name/title of the affected resource
    old_values = Column(Text)  # JSON string of old values (for updates)
    new_values = Column(Text)  # JSON string of new values (for creates/updates)
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    session_id = Column(String(255))
    request_id = Column(String(255))  # For tracing requests
    details = Column(Text)  # Additional details about the action
    success = Column(String(10), default="true")  # 'true', 'false', or 'partial'
    error_message = Column(Text)  # Error details if action failed
    duration_ms = Column(Integer)  # How long the action took
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action='{self.action}', resource='{self.resource_type}')>"

    @classmethod
    def log_action(
        cls,
        user_id: Optional[int],
        action: AuditAction,
        resource_type: str,
        resource_id: Optional[int] = None,
        resource_name: Optional[str] = None,
        old_values: Optional[dict] = None,
        new_values: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        details: Optional[str] = None,
        success: str = "true",
        error_message: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ) -> "AuditLog":
        """Helper method to create audit log entries"""
        import json
        
        return cls(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            old_values=json.dumps(old_values) if old_values else None,
            new_values=json.dumps(new_values) if new_values else None,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            request_id=request_id,
            details=details,
            success=success,
            error_message=error_message,
            duration_ms=duration_ms,
        )