from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


class CertificateStatus(str, Enum):
    PENDING = "pending"
    ISSUED = "issued"
    VALID = "valid"  # Alias for issued
    REVOKED = "revoked"
    EXPIRED = "expired"


# Certificate Schemas
class CertificateBase(BaseModel):
    user_id: int
    course_id: Optional[int] = None
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    score_achieved: Optional[float] = None
    completion_date: datetime
    expiry_date: Optional[datetime] = None
    template_used: Optional[str] = Field(None, max_length=100)
    additional_data: Optional[str] = None  # JSON string


class CertificateCreate(CertificateBase):
    pass


class CertificateUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    score_achieved: Optional[float] = None
    completion_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    status: Optional[CertificateStatus] = None
    template_used: Optional[str] = Field(None, max_length=100)
    additional_data: Optional[str] = None


class CertificateResponse(CertificateBase):
    id: int
    certificate_number: str
    status: CertificateStatus
    issue_date: datetime
    file_path: Optional[str] = None
    verification_code: Optional[str] = None
    template_used: Optional[str] = None
    issued_by: Optional[int] = None
    revoked_by: Optional[int] = None
    revoked_at: Optional[datetime] = None
    revocation_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    is_valid: bool
    is_expired: bool

    class Config:
        from_attributes = True


# User and Course info for certificate list
class UserInfo(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    document_number: Optional[str] = None
    
    @property
    def name(self) -> str:
        return f"{self.first_name} {self.last_name}"
    
    class Config:
        from_attributes = True

class CourseInfo(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    
    class Config:
        from_attributes = True

class CertificateListResponse(BaseModel):
    id: int
    certificate_number: str
    title: str
    user_id: int
    course_id: Optional[int] = None
    status: CertificateStatus
    issue_date: datetime
    issued_date: Optional[datetime] = Field(None, alias='issue_date')  # Alias for frontend compatibility
    expiry_date: Optional[datetime] = None
    score_achieved: Optional[float] = None
    is_valid: bool
    is_expired: bool
    user: Optional[UserInfo] = None
    course: Optional[CourseInfo] = None

    class Config:
        from_attributes = True
        populate_by_name = True


# Certificate Verification Schema
class CertificateVerification(BaseModel):
    certificate_number: Optional[str] = None
    verification_code: Optional[str] = None


class CertificateVerificationResponse(BaseModel):
    is_valid: bool
    certificate: Optional[CertificateResponse] = None
    message: str


# Certificate Generation Schema
class CertificateGeneration(BaseModel):
    user_id: int
    course_id: Optional[int] = None
    score_achieved: Optional[float] = None
    completion_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    template_used: Optional[str] = "default"
    custom_data: Optional[dict] = None


# Certificate PDF Generation Schema
class CertificatePDFGeneration(BaseModel):
    user_id: int
    course_id: Optional[int] = None
    template_name: Optional[str] = "default"
    include_score: bool = True
    custom_message: Optional[str] = None