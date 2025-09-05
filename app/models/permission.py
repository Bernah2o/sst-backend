from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    resource_type = Column(String(50), nullable=False, index=True)
    action = Column(String(50), nullable=False, index=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    roles = relationship("CustomRole", secondary="role_permissions", back_populates="permissions")

    def __repr__(self):
        return f"<Permission(id={self.id}, resource_type='{self.resource_type}', action='{self.action}')>"

    @classmethod
    def get_permission_by_resource_action(cls, db, resource_type: str, action: str):
        """Get permission by resource type and action"""
        return db.query(cls).filter(
            cls.resource_type == resource_type,
            cls.action == action,
            cls.is_active == True
        ).first()