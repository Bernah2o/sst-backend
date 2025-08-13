from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    Float,
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property

from app.database import Base


class CertificateStatus(str, Enum):
    PENDING = "pending"
    ISSUED = "issued"
    VALID = "valid"  # Alias for issued
    REVOKED = "revoked"
    EXPIRED = "expired"


class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    certificate_number = Column(String(100), unique=True, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    score_achieved = Column(Float)
    completion_date = Column(DateTime, nullable=False)
    issue_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    expiry_date = Column(DateTime)  # Some certificates may expire
    status = Column(SQLEnum(CertificateStatus), default=CertificateStatus.PENDING)
    file_path = Column(String(500))  # Path to generated PDF certificate
    verification_code = Column(String(100), unique=True)  # For public verification
    template_used = Column(String(100))  # Template name used for generation
    additional_data = Column(Text)  # JSON string for additional certificate data
    issued_by = Column(Integer, ForeignKey("users.id"))  # Who issued the certificate
    revoked_by = Column(Integer, ForeignKey("users.id"))  # Who revoked it (if applicable)
    revoked_at = Column(DateTime)
    revocation_reason = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="certificates")
    course = relationship("Course", back_populates="certificates")
    issuer = relationship("User", foreign_keys=[issued_by])
    revoker = relationship("User", foreign_keys=[revoked_by])

    def __repr__(self):
        return f"<Certificate(id={self.id}, number='{self.certificate_number}', status='{self.status}')>"

    @hybrid_property
    def is_valid(self) -> bool:
        """Check if certificate is currently valid"""
        if self.status != CertificateStatus.ISSUED:
            return False
        
        if self.expiry_date and self.expiry_date < datetime.utcnow():
            return False
            
        return True

    @hybrid_property
    def is_expired(self) -> bool:
        """Check if certificate has expired"""
        return self.expiry_date and self.expiry_date < datetime.utcnow() if self.expiry_date else False